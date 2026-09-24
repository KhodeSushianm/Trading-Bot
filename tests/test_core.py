# -*- coding: utf-8 -*-
"""تست‌های واحد هستهٔ پلاگین (فاز ۱ معماری) — آفلاین، سریع، بدون DOM/نت.

اجرا:  python tests/test_core.py     (از ریشهٔ ریپو)
پوشش: contracts · manifest · registry · resolver · lifecycle · config-bridge
      · event-bus · pipeline-runner

سبک: مثل بقیهٔ تست‌های پروژه — اسکریپت ساده با assert و خلاصهٔ فارسی
(بدون pytest). هر بخش یک تابع؛ خروجی ۰ یعنی همه‌چیز سبز.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core import (CONTRACTS, STAGES, CircularDependencyError, EventBus,  # noqa: E402
                      Events, InvalidManifestError, InvalidTransitionError,
                      LifecycleManager, PipelineRunner, PluginFailure,
                      PluginManifest, PluginRegistry, PluginState, StageResult,
                      is_valid_contract_id, is_wellformed_contract_id,
                      plugin_config, plugin_enabled, resolve)
from src.core.contracts import MarketDataProvider  # noqa: E402

COUNT = 0


def A(cond: bool, msg: str) -> None:
    """assert شمارشی — تعداد بررسی‌های پاس‌شده را می‌شمارد."""
    global COUNT
    assert cond, msg
    COUNT += 1


def expect_raise(exc_type, fn, msg: str) -> Exception:
    try:
        fn()
    except exc_type as e:
        A(True, msg)
        return e
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"{msg} — انتظار {exc_type.__name__} بود، {type(e).__name__} گرفتیم: {e}")
    raise AssertionError(f"{msg} — هیچ استثنایی پرتاب نشد")


# ── پلاگین‌های ساختگی ──────────────────────────────────────────
def _mk(pid: str, provides: list, requires: list = None, stage: str = "collect_market",
        priority: int = 100, config: dict = None, factory=None) -> PluginManifest:
    return PluginManifest(id=pid, version="1.0.0", provides=provides,
                          requires=requires or [], stage=stage,
                          priority=priority, config=config, factory=factory)


class FakeInstance:
    def __init__(self, trace: list, name: str, fail_on: str = ""):
        self.trace, self.name, self.fail_on = trace, name, fail_on

    def initialize(self):
        if self.fail_on == "initialize":
            raise RuntimeError("boom-init")
        self.trace.append(f"{self.name}:init")

    def start(self):
        if self.fail_on == "start":
            raise RuntimeError("boom-start")
        self.trace.append(f"{self.name}:start")

    def run(self, ctx):
        if self.fail_on == "run":
            raise RuntimeError("boom-run")
        self.trace.append(f"{self.name}:run")
        return self.name


# ══════════════════════════════════════════════════════════════
def test_contracts() -> None:
    A(len(CONTRACTS) == 15, f"باید ۱۵ قرارداد باشد، {len(CONTRACTS)} است")
    for cid in CONTRACTS:
        A(is_valid_contract_id(cid), f"شناسهٔ قرارداد بدشکل: {cid}")
    A(not is_valid_contract_id("odin.foo@1"), "قرارداد ثبت‌نشده باید نامعتبر باشد")
    A(is_wellformed_contract_id("odin.foo@1"), "شکل صحیح ولی ناشناخته → wellformed")
    A(not is_wellformed_contract_id("bogus"), "شناسهٔ بی‌شکل باید رد شود")

    class FakeProvider:
        name = "fake"
        def connect(self): pass
        def disconnect(self): pass
        def fetch(self, sym_cfg): return None

    A(isinstance(FakeProvider(), MarketDataProvider),
      "Protocol ساختاری: fake کامل باید MarketDataProvider باشد")

    class Broken:
        def connect(self): pass

    A(not isinstance(Broken(), MarketDataProvider),
      "fake ناقص (بدون fetch/disconnect) نباید قرارداد را ارضا کند")


def test_manifest() -> None:
    m = _mk("good-plugin", ["odin.session@1"])
    A(m.validate() is m, "مانیفست معتبر باید validate را پاس کند")

    expect_raise(InvalidManifestError,
                 lambda: _mk("Bad ID!", ["odin.session@1"]).validate(),
                 "id با فاصله/حرف بزرگ باید رد شود")
    expect_raise(InvalidManifestError,
                 lambda: PluginManifest(id="x", version="1.0", provides=["odin.session@1"],
                                        stage="judge").validate(),
                 "نسخهٔ غیر-semver باید رد شود")
    expect_raise(InvalidManifestError,
                 lambda: PluginManifest(id="x", version="1.0.0", provides=[],
                                        stage="judge").validate(),
                 "provides خالی باید رد شود")
    expect_raise(InvalidManifestError,
                 lambda: _mk("x", ["odin.unknown@1"]).validate(),
                 "قرارداد ناشناخته باید رد شود — هسته فقط CONTRACTS را می‌شناسد")
    expect_raise(InvalidManifestError,
                 lambda: _mk("x", ["odin.session@1"], requires=["odin.session@1"]).validate(),
                 "وابستگی به قراردادِ خودش باید رد شود")
    expect_raise(InvalidManifestError,
                 lambda: PluginManifest(id="x", version="1.0.0", provides=["odin.session@1"],
                                        stage="judge", platforms=["ios"]).validate(),
                 "پلتفرم نامعتبر باید رد شود")
    expect_raise(InvalidManifestError,
                 lambda: PluginManifest(id="x", version="1.0.0", provides=["odin.session@1"],
                                        stage="").validate(),
                 "stage خالی باید رد شود")
    expect_raise(InvalidManifestError,
                 lambda: PluginManifest(id="x", version="1.0.0", provides=["odin.session@1"],
                                        stage="nonexistent").validate(known_stages=STAGES),
                 "مرحلهٔ ناشناخته (با known_stages) باید رد شود")
    expect_raise(InvalidManifestError,
                 lambda: PluginManifest(id="x", version="1.0.0", provides=["odin.session@1"],
                                        stage="judge", config={"default": True}).validate(),
                 "config بدون section/enabled_key باید رد شود")


def test_registry() -> None:
    reg = PluginRegistry(known_stages=STAGES)
    reg.register(_mk("data-yahoo", ["odin.data.market@1"], priority=20))
    reg.register(_mk("data-auto", ["odin.data.market@1"], priority=10))
    reg.register(_mk("analysis", ["odin.analysis.technical@1"]))

    A(len(reg.all()) == 3, "سه پلاگین باید ثبت شوند")
    got = reg.get("odin.data.market@1")
    A(got is not None and got.id == "data-auto",
      "get() باید بالاترین اولویت (عدد کوچک‌تر) را برگرداند")
    ids = [r.id for r in reg.providers("odin.data.market@1")]
    A(ids == ["data-auto", "data-yahoo"], f"ترتیب قطعی providers اشتباه است: {ids}")

    reg.disable("data-auto")
    A(reg.get("odin.data.market@1").id == "data-yahoo",
      "پلاگین غیرفعال نباید از get() برگردد")
    reg.enable("data-auto")
    A(reg.get("odin.data.market@1").id == "data-auto", "enable باید برگرداند")

    expect_raise(Exception, lambda: reg.register(_mk("data-yahoo", ["odin.data.market@1"])),
                 "ثبت id تکراری باید خطا بدهد")
    A(reg.get("odin.notify@1") is None, "قرارداد بدون فراهم‌کننده → None (نه استثنا)")

    st = {s["id"]: s for s in reg.status()}
    A(st["analysis"]["state"] == "registered", "status() باید وضعیت فعلی را بدهد")
    expect_raise(InvalidManifestError,
                 lambda: reg.register(_mk("bad-stage", ["odin.session@1"], stage="nope")),
                 "ثبت با stage نامعتبر (known_stages) باید رد شود")


def test_resolver() -> None:
    reg = PluginRegistry(known_stages=STAGES)
    rec_s = reg.register(_mk("session", ["odin.session@1"]))
    rec_c = reg.register(_mk("calendar", ["odin.fundamental.calendar@1"],
                             requires=["odin.session@1"]))
    order = resolve(reg.all())
    A([r.id for r in order] == ["session", "calendar"],
      "ترتیب توپولوژیک: فراهم‌کننده قبل از وابسته")
    A(rec_s.state is PluginState.RESOLVED and rec_c.state is PluginState.RESOLVED,
      "resolve باید وضعیت RESOLVED بگذارد")

    # وابستگی مفقود → disabled با دلیل فارسی، بدون استثنا
    reg2 = PluginRegistry(known_stages=STAGES)
    rec_tv = reg2.register(_mk("tv-user", ["odin.report@1"], requires=["odin.data.tv@1"]))
    order2 = resolve(reg2.all())
    A(rec_tv not in order2, "پلاگین با وابستگی مفقود نباید در زنجیره باشد")
    A(bool(rec_tv.disabled_reason) and "odin.data.tv@1" in rec_tv.disabled_reason,
      f"دلیل فارسی/شفاف ثبت نشده: {rec_tv.disabled_reason!r}")
    A(rec_tv.active is False, "پلاگین وابسته‌مفقود باید inactive باشد")

    # آبشاری: غیرفعال‌شدن A باید B (وابسته به A) را هم بیندازد
    reg3 = PluginRegistry(known_stages=STAGES)
    reg3.register(_mk("a-x", ["odin.data.tv@1"], requires=["odin.session@1"]))  # session نیست
    rec_b = reg3.register(_mk("b-x", ["odin.report@1"], requires=["odin.data.tv@1"]))
    order3 = resolve(reg3.all())
    A(order3 == [] and rec_b.disabled_reason, "غیرفعال‌شدن آبشاری باید هر دو را بیندازد")

    # پلاگین enabled=False از دید وابسته‌ها «نبود» است
    reg4 = PluginRegistry(known_stages=STAGES)
    rec_off = reg4.register(_mk("off-session", ["odin.session@1"]))
    rec_dep = reg4.register(_mk("dep-x", ["odin.analysis.technical@1"],
                                requires=["odin.session@1"]))
    reg4.disable("off-session")
    resolve(reg4.all())
    A(rec_off not in [r for r in reg4.all() if r.state is PluginState.RESOLVED]
      or not rec_off.enabled, "پلاگین خاموش نباید resolve شود")
    A(bool(rec_dep.disabled_reason), "وابستهٔ پلاگین خاموش باید دلیل بگیرد")

    # حلقه → پرسروصدا با نام هر دو
    reg5 = PluginRegistry(known_stages=STAGES)
    reg5.register(_mk("loop-a", ["odin.session@1"], requires=["odin.data.market@1"]))
    reg5.register(_mk("loop-b", ["odin.data.market@1"], requires=["odin.session@1"]))
    e = expect_raise(CircularDependencyError, lambda: resolve(reg5.all()),
                     "حلقهٔ وابستگی باید پرسروصدا باشد")
    A("loop-a" in str(e) and "loop-b" in str(e), "پیام حلقه باید مسیر/نام‌ها را داشته باشد")


def test_lifecycle() -> None:
    trace: list = []
    reg = PluginRegistry(known_stages=STAGES)
    good = reg.register(_mk("life-good", ["odin.session@1"],
                            factory=lambda: FakeInstance(trace, "good")))
    bad = reg.register(_mk("life-bad", ["odin.analysis.technical@1"],
                           factory=lambda: FakeInstance(trace, "bad", fail_on="initialize")))
    resolve(reg.all())

    failures_seen: list = []
    lm = LifecycleManager(on_failure=failures_seen.append)
    failures = lm.initialize_all([good, bad], start=True)

    A(good.state is PluginState.STARTED, "پلاگین سالم باید STARTED شود")
    A(bad.state is PluginState.FAILED, "پلاگین خراب باید قرنطینه (FAILED) شود")
    A(trace == ["good:init", "good:start"], f"بدِ خراب نباید trace بگذارد: {trace}")
    A(len(failures) == 1 and failures[0].plugin_id == "life-bad"
      and failures[0].phase == "initialize", "PluginFailure باید دقیق ثبت شود")
    A("boom-init" in bad.error, "جزئیات خطا باید روی رکورد بماند")
    A("life-bad" in failures_seen[0].fa_message(), "پیام فارسی قرنطینه باید id داشته باشد")

    # گذار نامعتبر = باگ چارچوب → پرسروصدا
    fresh = PluginRegistry(known_stages=STAGES).register(_mk("fresh", ["odin.session@1"]))
    expect_raise(InvalidTransitionError, lambda: lm.start(fresh),
                 "start روی REGISTERED باید InvalidTransitionError بدهد")

    # stop → dispose
    A(lm.stop(good) is None and good.state is PluginState.STOPPED, "stop باید کار کند")
    A(lm.dispose(good) is None and good.state is PluginState.DISPOSED
      and good.instance is None, "dispose باید نمونه را رها کند")


def test_config_bridge() -> None:
    m_news = _mk("fundamental-news", ["odin.fundamental.news@1"],
                 config={"section": "news", "enabled_key": "enabled", "default": True})

    # روی config.yaml واقعی پروژه (اگر yaml هست) + dict دست‌ساز
    cfg = None
    try:
        import yaml
        p = ROOT / "config.yaml"
        if p.exists():
            cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    except ImportError:
        cfg = None
    if cfg is None:
        cfg = {"news": {"enabled": True, "min_score": 2}}

    A(plugin_enabled(cfg, m_news) is True, "news.enabled=true → فعال")
    off = dict(cfg)
    off["news"] = dict(cfg.get("news") or {}, enabled=False)
    A(plugin_enabled(off, m_news) is False, "news.enabled=false → غیرفعال")
    over = dict(off)
    over["plugins"] = {"fundamental-news": {"enabled": True}}
    A(plugin_enabled(over, m_news) is True, "override صریح plugins باید برنده شود")

    m_def = _mk("x-def", ["odin.session@1"],
                config={"section": "not_in_cfg", "enabled_key": "enabled", "default": False})
    A(plugin_enabled(cfg, m_def) is False, "بخش مفقود → پیش‌فرض مانیفست")
    m_none = _mk("x-none", ["odin.session@1"])
    A(plugin_enabled(cfg, m_none) is True, "بدون اتصال config → فعال")

    sec = plugin_config(cfg, _mk("n", ["odin.fundamental.news@1"],
                                 config={"section": "news", "enabled_key": "enabled"}))
    A(isinstance(sec, dict), "plugin_config باید dict بدهد")
    A(plugin_config(cfg, m_none) == {}, "بدون section → dict خالی")

    # ── فاز ۷: enabled_key نقطه‌ای (dot-path) برای کلیدهای تودرتوی *موجود* ──
    m_veto = _mk("veto-weekend-x", ["odin.judge.veto@1"],
                 config={"section": "judge", "enabled_key": "veto.weekend", "default": True})
    A(plugin_enabled({"judge": {"veto": {"weekend": False}}}, m_veto) is False,
      "dot-path: judge.veto.weekend=false → غیرفعال")
    A(plugin_enabled({"judge": {"veto": {"weekend": True}}}, m_veto) is True,
      "dot-path: judge.veto.weekend=true → فعال")
    A(plugin_enabled({"judge": {}}, m_veto) is True,
      "dot-path مفقود → پیش‌فرض مانیفست (default=True)")
    A(plugin_enabled({"judge": {"veto": {}}}, m_veto) is True,
      "dot-path نیمه‌مفقود → پیش‌فرض مانیفست")
    A(plugin_enabled({"judge": {"veto": {"weekend": True}},
                      "plugins": {"veto-weekend-x": {"enabled": False}}}, m_veto) is False,
      "override صریح plugins بر dot-path هم برنده است")


def test_bus() -> None:
    bus = EventBus()
    seen: list = []

    def l1(_p): raise RuntimeError("bad-listener")
    def l2(p): seen.append(("l2", p))

    bus.on(Events.JUDGE_DONE, l1)
    off = bus.on(Events.JUDGE_DONE, l2)
    A(bus.listener_count(Events.JUDGE_DONE) == 2, "دو listener ثبت شد")

    errors = bus.emit(Events.JUDGE_DONE, {"score": 9})
    A(len(errors) == 1 and errors[0][0] is l1, "خطای listener باید جمع شود، نه پرتاب")
    A(seen == [("l2", {"score": 9})], "listener خراب نباید سالم را بشکند")

    off()
    A(bus.listener_count(Events.JUDGE_DONE) == 1, "unsubscribe باید کم کند")
    A(bus.emit("event.naamoshakhas") == [], "رویداد ناشناخته → بدون خطا")
    A(all(isinstance(e, str) for e in Events.ALL) and len(set(Events.ALL)) == len(Events.ALL),
      "نام رویدادها باید str و یکتا باشند")


def test_pipeline() -> None:
    reg = PluginRegistry(known_stages=STAGES)
    trace: list = []

    # پلاگین واقعیِ مرحلهٔ judge با هوک run
    rec = reg.register(_mk("judge-plugin", ["odin.judge.engine@1"], stage="judge",
                           factory=lambda: FakeInstance(trace, "judge")))
    resolve(reg.all())
    lm = LifecycleManager()
    lm.initialize_all([rec], start=True)
    A(rec.state is PluginState.STARTED, "پلاگین pipeline باید STARTED باشد")

    bus = EventBus()
    stages_seen: list = []
    bus.on(Events.STAGE_DONE, lambda p: stages_seen.append(p["stage"]))

    runner = PipelineRunner(registry=reg, bus=bus)
    order: list = []
    runner.add("collect_market", lambda ctx: order.append("m1") or "m1", priority=20)
    runner.add("collect_market", lambda ctx: order.append("m0") or "m0", priority=10)
    runner.add("render", lambda ctx: (_ for _ in ()).throw(RuntimeError("render-boom")))

    res = runner.run({})
    A(order == ["m0", "m1"], f"اولویت smaller-first رعایت نشد: {order}")
    cm = res.stage("collect_market")
    A(cm is not None and cm.ok, "مرحلهٔ سالم باید ok باشد")

    rd = res.stage("render")
    A(rd is not None and rd.unavailable and not rd.ok and "render-boom" in rd.error,
      "خطای مرحله → unavailable (نه کرش) و ادامهٔ pipeline")
    A(res.stage("dashboard") is not None, "مراحل بعد از خطا هم باید اجرا شوند")
    A("judge" in stages_seen,
      "رویداد stage.done برای judge باید منتشر شود")
    A(trace == ["judge:init", "judge:start", "judge:run"],
      f"هوک run پلاگینِ مرحله باید در جریان pipeline صدا شود: {trace}")

    # خروج زودهنگام (early-exit امروزِ run_cycle)
    r2 = PipelineRunner()
    r2.add("journal_pre", lambda ctx: StageResult(stage="journal_pre", stop=True,
                                                  value="no-analyses"))
    res2 = r2.run({})
    A(res2.stopped_at == "journal_pre", "stop=True باید pipeline را زود ببندد")
    A(res2.stage("judge") is None, "بعد از stop هیچ مرحله‌ای نباید اجرا شود")

    # ترتیب STAGES == ترتیب چرخهٔ فعلی (مرجع: run_cycle در src/engine.py)
    A(STAGES[0] == "collect_market" and STAGES[1] == "journal_pre"
      and STAGES[2] == "collect_fundamental" and STAGES[-1] == "archive_notify",
      "ترتیب مراحل باید با چرخهٔ فعلی یکی باشد (فاندامنتال بعد از early-exit)")


# ══════════════════════════════════════════════════════════════
def main() -> int:
    tests = [test_contracts, test_manifest, test_registry, test_resolver,
             test_lifecycle, test_config_bridge, test_bus, test_pipeline]
    fails = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fails.append(f"{t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            fails.append(f"{t.__name__}: خطای غیرمنتظره {type(e).__name__}: {e}")
    if fails:
        print("❌ CORE TESTS FAILED")
        for f in fails:
            print("  •", f)
        return 1
    print(f"✅ CORE TESTS OK — {COUNT} بررسی پاس؛ "
          f"قراردادها/مانیفست/registry/resolver/lifecycle/config/bus/pipeline سالم")
    return 0


if __name__ == "__main__":
    sys.exit(main())
