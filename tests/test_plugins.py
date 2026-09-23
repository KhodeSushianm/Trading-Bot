# -*- coding: utf-8 -*-
"""تست‌های طلایی پلاگین‌های داخلی (فاز ۲ + قواعد داورِ فاز ۴) — آفلاین، سریع.

اجرا:  python tests/test_plugins.py     (از ریشهٔ ریپو)

ایدهٔ «تست طلایی»: خروجی هر adapter باید **دقیقاً** برابر خروجی فراخوانی
مستقیم همان تابع/کلاس موجود باشد (ورودی دست‌سازِ ثابت). adapterها فقط
delegation‌اند؛ هر اختلاف = تغییر رفتار = شکست.

فاز ۴ — دو طلاییِ اضافه برای rule-pluginهای داور:
  ۱) هر ۱۵ adapter قاعده (۷ وتو + ۸ شاهد) + judge-risk == فراخوانی مستقیم،
     و ترتیب providers(veto@1/evidence@1) == ترتیب ارزیابیِ امروز (priority).
  ۲) باتری کامل سناریوهای داوری از مسیر registry (JudgePlugin + rules) ==
     فایل طلاییِ tests/golden/judge_rules_golden.json — بایت‌به‌بایت.

توابع شبکه‌ای (fetch_calendar/fetch_tv_snapshot/telegram.send_message) با
mock sentinel تست می‌شوند: هم «چه تابعی» و هم «با چه آرگومان‌هایی» صدا زده شد.
منابع داده (Yahoo/TD/Auto) فقط اگر yfinance نصب باشد تا سطح «نوع کلاس»
تست می‌شوند؛ در CI (بدون yfinance) فقط نگاشت انتخاب و پیام‌های خطا سنجیده
می‌شوند — که همان‌ها فاز ۳ مصرف می‌کند.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import math
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config                                   # noqa: E402
from src.core.contracts import CONTRACTS                             # noqa: E402
from src.core.lifecycle import LifecycleManager, PluginState         # noqa: E402
from src.plugins import build_default_registry                       # noqa: E402
from src.plugins.alerts import PriceAlertsPlugin                     # noqa: E402
from src.plugins.analysis import StrengthPlugin, TechnicalPlugin     # noqa: E402
from src.plugins.data import select_market_provider                  # noqa: E402
from src.plugins.fundamental import CalendarPlugin, NewsPlugin       # noqa: E402
from src.plugins.journal import JournalPlugin                        # noqa: E402
from src.plugins.judge import (EVIDENCE_RULES, VETO_RULES,           # noqa: E402
                               EvidenceRuleAdapter, JudgePlugin,
                               RiskPlugin, SessionPlugin,
                               VetoRuleAdapter)
from src.plugins.report import KINDS, ReportRendererPlugin           # noqa: E402

COUNT = 0
NOW = datetime(2026, 9, 16, 14, 30, tzinfo=timezone.utc)   # چهارشنبه — هم‌پوشانی لندن/NY


def A(cond: bool, msg: str) -> None:
    global COUNT
    assert cond, msg
    COUNT += 1


def same(a, b) -> bool:
    """برابری عمیق با تحمل NaN (مثل numEq در run_parity.js)."""
    if isinstance(a, float) or isinstance(b, float):
        try:
            fa, fb = float(a), float(b)
        except (TypeError, ValueError):
            return a == b
        if math.isnan(fa) and math.isnan(fb):
            return True
        return fa == fb
    if dataclasses.is_dataclass(a) and not isinstance(a, type):
        return (dataclasses.is_dataclass(b) and not isinstance(b, type)
                and same(dataclasses.asdict(a), dataclasses.asdict(b)))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return bool(a == b)


CFG = load_config()


def _mk_frame(n: int, base: float, freq: str):
    import pandas as pd
    idx = pd.date_range("2026-08-01", periods=n, freq=freq)
    close = [base + 0.00012 * ((i * 7) % 11 - 5) for i in range(n)]
    return pd.DataFrame({"Open": [c - 0.0001 for c in close],
                         "High": [c + 0.0004 for c in close],
                         "Low": [c - 0.0004 for c in close],
                         "Close": close}, index=idx)


def _mk_md(symbol: str, base: float):
    from src.data.base import MarketData
    return MarketData(symbol=symbol,
                      m15=_mk_frame(260, base, "15min"),
                      h1=_mk_frame(260, base, "1h"),
                      h4=_mk_frame(260, base, "4h"))


def _mk_snapshot():
    from src.fundamental.calendar import CalendarEvent, CalendarSnapshot
    evs = [
        CalendarEvent(when=NOW + timedelta(minutes=25), country="USD",
                      title="Federal Funds Rate", title_fa="نرخ بهرهٔ فدرال",
                      impact="HIGH", forecast="4.00%", previous="4.00%",
                      category="نرخ بهره و بانک مرکزی", polarity=1, source="t"),
        CalendarEvent(when=NOW + timedelta(hours=20), country="EUR",
                      title="CPI y/y", title_fa="تورم سالانه (CPI)",
                      impact="HIGH", forecast="2.1%", previous="2.0%",
                      category="تورم و قیمت‌ها", polarity=1, source="t"),
    ]
    return CalendarSnapshot(events=evs, source="t")


EXPECTED_IDS = {
    "data-auto", "data-yahoo", "data-twelvedata", "data-tradingview",
    "analysis-technical", "analysis-strength", "session",
    "fundamental-calendar", "fundamental-news", "judge-core", "judge-risk",
    "journal", "notify-telegram", "alerts-price", "report-renderer",
    # فاز ۴ — rule-pluginهای داور (idها دقیقاً از جدول قراردادهای سند معماری)
    "veto-data", "veto-weekend", "veto-tf-conflict", "veto-range",
    "veto-event", "veto-vol-spike", "veto-breaking-news",
    "ev-trend", "ev-level", "ev-fundamental", "ev-momentum",
    "ev-strength", "ev-news", "ev-tv", "ev-session",
}
# از فاز ۴ همهٔ قراردادها فراهم‌کننده دارند (veto@1/evidence@1 پر شدند)
PROVIDED_NOW = set(CONTRACTS)

# ترتیب ارزیابیِ قواعد — همان ترتیبِ collect_vetoes/جدول امتیازِ امروز،
# پین‌شده با priority مانیفست‌ها (veto-data=10 … ev-session=80)
VETO_ORDER = ["veto-data", "veto-weekend", "veto-tf-conflict", "veto-range",
              "veto-event", "veto-vol-spike", "veto-breaking-news"]
EVIDENCE_ORDER = ["ev-trend", "ev-level", "ev-fundamental", "ev-momentum",
                  "ev-strength", "ev-news", "ev-tv", "ev-session"]


# ══════════════════════════════════════════════════════════════
def test_registration() -> None:
    reg, info = build_default_registry(CFG)
    ids = {r.id for r in reg.all()}
    A(ids == EXPECTED_IDS, f"مجموعهٔ پلاگین‌های ثبت‌شده فرق کرد: {ids ^ EXPECTED_IDS}")
    A(len(info["log"]) >= len(EXPECTED_IDS), "لاگ ثبت باید به‌ازای هر پلاگین خط داشته باشد")
    A(info["disabled"] == [], f"با config واقعی هیچ پلاگینی نباید disabled شود: {info['disabled']}")
    A(len(info["order"]) == len(EXPECTED_IDS), "resolve باید همه را بچیند")

    for cid in PROVIDED_NOW:
        A(len(reg.providers(cid)) >= 1, f"قرارداد {cid} بدون فراهم‌کننده است")
    # فاز ۴: veto@1/evidence@1 پر شدند — ترتیب providers == ترتیب ارزیابیِ
    # امروز (priority پین می‌کند؛ جزئیات بایت‌به‌بایت در test_judge_rule_plugins)
    A([r.id for r in reg.providers("odin.judge.veto@1")] == VETO_ORDER,
      "ترتیب فراهم‌کنندگان veto@1 باید DATA→…→BREAKING_NEWS بماند")
    A([r.id for r in reg.providers("odin.judge.evidence@1")] == EVIDENCE_ORDER,
      "ترتیب فراهم‌کنندگان evidence@1 باید trend→…→session بماند")

    # وضعیت فعال‌بودن == کلیدهای موجود config (بدون کلید جدید)
    A(reg.by_id("fundamental-news").enabled is True, "news.enabled=true → فعال")
    A(reg.by_id("notify-telegram").enabled is True,
      "notify همیشه فعال است (guard «تنظیم نشده» داخل بدنهٔ send است — فاز ۳)")
    A(reg.by_id("fundamental-calendar").manifest.config["section"] == "fundamental",
      "تقویم باید به کلید fundamental.enabled متصل باشد")

    # lifecycle روی یک پلاگین سبک (session) — بدون yfinance/نت
    rec = reg.by_id("session")
    lm = LifecycleManager(context=info["context"])
    A(lm.initialize(rec) is None and rec.state is PluginState.INITIALIZED,
      "initialize پلاگین session باید سالم باشد")
    A(lm.start(rec) is None and rec.state is PluginState.STARTED, "start باید سالم باشد")
    A(isinstance(rec.instance, SessionPlugin), "نمونه باید همان کلاس adapter باشد")

    # platform filter
    reg_a, info_a = build_default_registry(CFG, platform="android")
    ids_a = {r.id for r in reg_a.all()}
    A("notify-telegram" not in ids_a, "تلگرام desktop-only است")
    A(not (ids_a & {"data-auto", "data-yahoo", "data-twelvedata", "data-tradingview"}),
      "منابع دادهٔ پایتون desktop-only هستند (JS مالِ فاز ۶)")
    A({"judge-core", "judge-risk", "journal", "alerts-price"} <= ids_a,
      "پلاگین‌های مشترک باید باشند")
    A(set(VETO_ORDER) | set(EVIDENCE_ORDER) <= ids_a,
      "قواعد داور (وتو/شاهد) در اندروید هم ثبت می‌شوند")


def test_enable_disable() -> None:
    import copy
    cfg2 = copy.deepcopy(CFG)
    cfg2["news"]["enabled"] = False
    reg, info = build_default_registry(cfg2)
    A(reg.by_id("fundamental-news").enabled is False, "news.enabled=false → پلاگین خاموش")
    A(reg.get("odin.fundamental.news@1") is None, "get() نباید پلاگین خاموش را بدهد")
    A(reg.by_id("fundamental-calendar").enabled is True, "خاموشی اخبار نباید به تقویم سرایت کند")
    A(any("طبق تنظیمات غیرفعال" in ln for ln in info["log"]), "لاگ فارسی غیرفعال‌سازی باید باشد")


def test_select_market_provider() -> None:
    reg, _ = build_default_registry(CFG)
    rec = select_market_provider(reg, CFG)          # data_source: auto
    A(rec.id == "data-auto", f"auto باید data-auto را انتخاب کند، {rec.id} شد")

    # پیام‌های خطا باید بایت‌به‌بایت با get_source یکی باشند
    from src.data import get_source
    for bad in ("mt5", "binance"):
        try:
            get_source({**CFG, "data_source": bad})
            raise AssertionError(f"get_source({bad}) باید خطا بدهد")
        except ValueError as e_direct:
            try:
                select_market_provider(reg, {**CFG, "data_source": bad})
                raise AssertionError(f"select({bad}) باید خطا بدهد")
            except ValueError as e_plugin:
                A(str(e_direct) == str(e_plugin),
                  f"پیام خطای منبع «{bad}» باید یکسان باشد")

    # در صورت نصب yfinance: نوع نمونهٔ ساخته‌شده هم باید یکی باشد
    if importlib.util.find_spec("yfinance") is not None:
        ctx = {"cfg": CFG}
        A(type(rec.factory(ctx)) is type(get_source(CFG)),
          "factory پلاگین باید همان کلاس get_source را بسازد")
    else:
        A(True, "yfinance نیست — تست نوع منبع داده skip شد (CI)")


def test_golden_pure() -> None:
    # ── market_status ──
    from src.judge.session import market_status
    sp = SessionPlugin()
    moments = [NOW,                                     # چهارشنبه، هم‌پوشانی
               datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc),   # شنبه
               datetime(2026, 9, 15, 3, 0, tzinfo=timezone.utc),    # توکیو
               datetime(2026, 9, 18, 21, 30, tzinfo=timezone.utc)]  # جمعه پس از NY
    for m in moments:
        A(same(sp.market_status(m), market_status(m)), f"market_status({m}) فرق کرد")

    # ── compute_levels (ریاضی SL/TP) — از فاز ۴ در پلاگین جداگانهٔ judge-risk ──
    from src.judge.scoring import compute_levels, judge_all, judge_config, JudgeContext
    jp = JudgePlugin()
    rp = RiskPlugin()
    rcfg = judge_config(CFG)["risk"]
    cases = [("BUY", 1.1000, 0.0012, 1.0990, 1.1050),
             ("SELL", 150.50, 0.25, None, 151.00),
             ("BUY", 2400.0, 15.0, 2395.0, None)]
    for c in cases:
        A(same(rp.compute_levels(*c, rcfg), compute_levels(*c, rcfg)),
          f"judge-risk: compute_levels{c} فرق کرد")
    A(not hasattr(jp, "compute_levels"),
      "judge-core از فاز ۴ فقط قرارداد engine است (risk تفکیک شد)")

    # ── judge_config + judge_all (خالی اما ctx واقعی) ──
    A(same(jp.judge_config(CFG), judge_config(CFG)), "judge_config باید یکسان باشد")
    ctx = JudgeContext(jcfg=judge_config(CFG), acfg=CFG["analysis"],
                       symbols_cfg=CFG["symbols"], ranking=[], tv_map={},
                       cal_snap=_mk_snapshot(), news_snap=None, now=NOW,
                       status=market_status(NOW), event_veto_minutes=30.0)
    A(jp.judge_all([], {}, ctx) == judge_all([], {}, ctx) == [],
      "judge_all با فهرست خالی باید [] بدهد (هر دو مسیر)")

    # ── تقویم: veto_for_symbol / upcoming_events ──
    from src.fundamental.calendar import upcoming_events, veto_for_symbol
    cp = CalendarPlugin()
    snap = _mk_snapshot()
    v_direct = veto_for_symbol(snap, "EUR", "USD", NOW, minutes=30.0)
    v_plugin = cp.veto_for_symbol(snap, "EUR", "USD", NOW, minutes=30.0)
    A([e.key for e in v_direct] == [e.key for e in v_plugin] and len(v_direct) == 1,
      "وتوی رویداد نزدیک (۲۵ دقیقه) باید هر دو مسیر یکی باشد")
    u_direct = upcoming_events(snap, NOW, hours=48.0, limit=6)
    u_plugin = cp.upcoming_events(snap, NOW, hours=48.0, limit=6)
    A([e.key for e in u_direct] == [e.key for e in u_plugin] and len(u_direct) == 2,
      "upcoming_events باید هر دو مسیر یکی باشد")

    # ── analyze_symbol + currency_strength (دادهٔ دست‌ساز قطعی) ──
    from src.analysis.technical import analyze_symbol
    from src.analysis.strength import currency_strength
    md = _mk_md("EURUSD", 1.10)
    sym_cfg = CFG["symbols"][0]
    a_direct = analyze_symbol(sym_cfg, md, CFG["analysis"])
    a_plugin = TechnicalPlugin().analyze_symbol(sym_cfg, md, CFG["analysis"])
    A(same(a_direct, a_plugin), "analyze_symbol باید بایت‌به‌بایت یکی باشد")

    datasets = {"EURUSD": md, "GBPUSD": _mk_md("GBPUSD", 1.30),
                "USDJPY": _mk_md("USDJPY", 150.0)}
    r_direct = currency_strength(datasets, lookback_h1=24)
    r_plugin = StrengthPlugin().currency_strength(datasets, lookback_h1=24)
    A(same(r_direct, r_plugin) and len(r_direct) >= 4, "currency_strength باید یکی باشد")

    # ── اخبار: مسیر آفلاین (enabled=false) — snapshot خطا، بدون شبکه ──
    import copy
    from src.fundamental.news import fetch_news
    cfg_off = copy.deepcopy(CFG)
    cfg_off["news"]["enabled"] = False
    n_direct = fetch_news(cfg_off)
    n_plugin = NewsPlugin().fetch_news(cfg_off)
    A(same(n_direct, n_plugin) and n_plugin.error == "غیرفعال در تنظیمات",
      "fetch_news مسیر غیرفعال باید یکی باشد (آفلاین)")


# ── هارنس طلاییِ داور (فاز ۴) — سازنده‌های سناریوی قطعی ──────────
def _load_judge_golden_module():
    spec = importlib.util.spec_from_file_location(
        "gen_judge_golden", ROOT / "tests" / "golden" / "gen_judge_golden.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_judge_rule_plugins() -> None:
    """طلاییِ فاز ۴: هر adapter قاعده == فراخوانی مستقیم + ترتیب/شناسه‌ها.

    دادهٔ سناریوها از هارنس طلایی داور (gen_judge_golden) — همان ورودی‌هایی
    که میخ‌های tests/test_judge_rules.py خروجی‌شان را پین کرده‌اند.
    """
    from src.judge import scoring
    gen = _load_judge_golden_module()
    reg, info = build_default_registry(CFG)

    # ── ترتیب و شناسه‌ها: دقیقاً جدول قراردادهای سند معماری ──
    A([r.id for r in reg.providers("odin.judge.veto@1")] == VETO_ORDER,
      "providers(veto@1) باید با ترتیب priority = ترتیب ارزیابی امروز بیاید")
    A([r.id for r in reg.providers("odin.judge.evidence@1")] == EVIDENCE_ORDER,
      "providers(evidence@1) باید با ترتیب priority = جدول امتیاز امروز بیاید")
    A([vid for _, vid, _ in VETO_RULES]
      == ["DATA", "WEEKEND", "TF_CONFLICT", "RANGE", "EVENT", "VOL_SPIKE",
          "BREAKING_NEWS"], "veto_idهای اعلانی = ۷ کلید فعلی Veto")
    A([eid for _, eid, _, _ in EVIDENCE_RULES]
      == ["TREND", "LEVEL", "FUNDAMENTAL", "MOMENTUM", "STRENGTH", "NEWS",
          "TV", "SESSION"], "evidence_idهای اعلانی = ۸ کلید فعلی Evidence")

    # ── تفکیک قراردادها: judge-core فقط engine، judge-risk فقط risk ──
    A(reg.by_id("judge-core").manifest.provides == ["odin.judge.engine@1"],
      "judge-core باید فقط odin.judge.engine@1 را فراهم کند")
    A(reg.by_id("judge-risk").manifest.provides == ["odin.judge.risk@1"],
      "judge-risk باید odin.judge.risk@1 را فراهم کند")
    A(reg.get("odin.judge.risk@1").id == "judge-risk",
      "get(risk@1) = judge-risk")

    # ── adapter == فراخوانی مستقیم: ۷ وتو روی دو ctx (چهارشنبه/شنبه) ──
    a = gen.make_analysis()
    md = gen.make_md()
    ctx_wed = gen.make_ctx(cal=gen.clean_cal(), news=gen.good_news())
    ctx_sat = gen.make_ctx(now=gen.SAT, cal=gen.near_cal(gen.SAT),
                           news=gen.breaking_news())
    for pid, vid, fname in VETO_RULES:
        rec = reg.by_id(pid)
        A(rec is not None and "odin.judge.veto@1" in rec.manifest.provides,
          f"{pid}: ثبت‌شده با قرارداد veto@1")
        inst = rec.factory(info["context"])
        A(isinstance(inst, VetoRuleAdapter) and inst.veto_id == vid,
          f"{pid}: veto_id باید {vid} باشد")
        for c in (ctx_wed, ctx_sat):
            direct = getattr(scoring, fname)(a, {}, md, c)
            got = inst.rule(a, {}, md, c)
            A((direct is None and got is None) or same(got, direct),
              f"{pid}: خروجی rule باید بایت‌به‌بایت {fname}() باشد")

    # ── adapter == فراخوانی مستقیم: ۸ شاهد در دو جهت ──
    for pid, eid, fname, ctx_only in EVIDENCE_RULES:
        rec = reg.by_id(pid)
        A(rec is not None and "odin.judge.evidence@1" in rec.manifest.provides,
          f"{pid}: ثبت‌شده با قرارداد evidence@1")
        inst = rec.factory(info["context"])
        A(isinstance(inst, EvidenceRuleAdapter) and inst.evidence_id == eid,
          f"{pid}: evidence_id باید {eid} باشد")
        fn = getattr(scoring, fname)
        for direction in ("BUY", "SELL"):
            direct = fn(ctx_wed) if ctx_only else fn(a, ctx_wed, direction)
            got = inst.rule(a, ctx_wed, direction)
            A(same(got, direct),
              f"{pid}: خروجی rule({direction}) باید بایت‌به‌بایت {fname}() باشد")

    # ── fallback بدون registry: delegation ساده (رفتار فاز ۲/۳a) ──
    from src.judge.scoring import judge_all
    jp_plain = JudgePlugin()                      # بدون context/registry
    A(jp_plain.judge_all([], {}, ctx_wed) == judge_all([], {}, ctx_wed) == [],
      "JudgePlugin بدون registry باید ساده delegate کند")


def test_judge_registry_parity() -> None:
    """طلاییِ کلانِ فاز ۴: باتری کامل سناریوها از مسیر rule-plugin ==
    فایل طلاییِ مسیر مستقیم (tests/golden/judge_rules_golden.json) —
    بایت‌به‌بایت، شامل متن‌های فارسی، ترتیب وتوها/شاهدها، امتیازها،
    ریاضی SL/TP، CAPPED و رکوردهای ژورنال."""
    gen = _load_judge_golden_module()
    golden_path = ROOT / "tests" / "golden" / "judge_rules_golden.json"
    A(golden_path.exists(), "فایل طلایی داور وجود ندارد")
    golden = json.loads(golden_path.read_text(encoding="utf-8"))

    reg, info = build_default_registry(CFG)
    jp = JudgePlugin(info["context"])             # registry-aware

    def j_sym(a, sym_cfg, md, ctx):
        # judge_symbol از مسیر پلاگین: judge_all تک‌نمادی همان معنا را دارد
        # (sym_cfg={} و datasets.get(symbol)=md — دقیقاً مثل judge_all)
        return jp.judge_all([a], {a.symbol: md}, ctx)[0]

    plugin_bat = gen.build_battery(judge_symbol_fn=j_sym,
                                   judge_all_fn=jp.judge_all)
    if plugin_bat != golden:
        diff = [k for k in sorted(set(plugin_bat) | set(golden))
                if plugin_bat.get(k) != golden.get(k)]
        raise AssertionError(
            f"باتریِ مسیر rule-plugin با طلایی فرق دارد — گروه‌های: {diff}")
    A(True, "باتری کامل داوری از مسیر registry == مسیر مستقیم (بایت‌به‌بایت)")

    # نمونهٔ lifecycle: judge-core از طریق _Caps-style initialize هم همان است
    lm = LifecycleManager(context=info["context"])
    rec = reg.by_id("judge-core")
    A(lm.initialize(rec) is None and rec.state is PluginState.INITIALIZED,
      "initialize پلاگین judge-core باید سالم باشد")
    A(isinstance(rec.instance, JudgePlugin), "نمونهٔ judge-core = JudgePlugin")


def test_delegation_network() -> None:
    """توابع شبکه‌ای: چه تابعی با چه آرگومان‌هایی — بدون هیچ درخواست واقعی."""
    cp = CalendarPlugin()
    with mock.patch("src.fundamental.calendar.fetch_calendar",
                    return_value="SENTINEL-CAL") as m:
        out = cp.fetch_calendar(CFG, use_cache=False, timeout=9)
        A(out == "SENTINEL-CAL", "خروجی delegate باید عیناً برگردد")
        m.assert_called_once_with(CFG, on_log=None, use_cache=False, timeout=9)
        A(True, "fetch_calendar با همان آرگومان‌های مستقیم صدا زده شد")

    from src.plugins.data import TvPlugin
    with mock.patch("src.data.tradingview.fetch_tv_snapshot",
                    return_value={"EURUSD": "TV"}) as m:
        syms = [{"name": "EURUSD"}]
        A(TvPlugin().fetch_tv_snapshot(syms, timeframe="1h", timeout=4) == {"EURUSD": "TV"},
          "TV delegate باید عیناً برگردد")
        m.assert_called_once_with(syms, timeframe="1h", timeout=4)
        A(True, "fetch_tv_snapshot با همان آرگومان‌ها صدا زده شد")

    # notify — از فاز ۳ بدنهٔ واقعی *داخل پلاگین* است (وارونِ delegation موقت
    # فاز ۲، همان‌طور که در Preview وعده داده شد)؛ engine._send_telegram
    # wrapper نازک شده و باید به پلاگین delegate کند.
    from src import engine
    from src.plugins.notify import TelegramNotifier
    cfg_on = {"telegram": {"send_reports": True, "bot_token": "123:fake",
                           "chat_id": "42"}}
    log_lines = []
    with mock.patch("src.notify.telegram.send_message", return_value=(True, "OK")) as m:
        out = TelegramNotifier().send(cfg_on, "متن", log_lines.append,
                                      "🎯 سیگنال EURUSD")
        A(out == (True, "OK"), "send پلاگین باید نتیجهٔ send_message را برگرداند")
        m.assert_called_once_with("123:fake", "42", "متن")
        A(log_lines[0] == "📱 ارسال 🎯 سیگنال EURUSD به تلگرام...",
          "لاگ ارسال پلاگین باید دقیق باشد")

    logs2 = []
    with mock.patch("src.notify.telegram.send_message", return_value=(True, "OK2")):
        A(engine._send_telegram(cfg_on, "x", logs2.append) == (True, "OK2"),
          "wrapper در engine باید به پلاگین notify delegate کند")


def test_golden_journal_alerts() -> None:
    import json
    from src.journal.stats import compute_stats
    from src.journal.store import Journal
    from src.journal.tracker import resolve_open_signals
    jp = JournalPlugin()

    with tempfile.TemporaryDirectory() as td:
        jpath = Path(td) / "signals.jsonl"
        j_plugin = jp.open(jpath)
        j_direct = Journal(jpath)
        A(j_plugin.path == j_direct.path, "open(path) باید همان مسیر Journal را بدهد")
        A(j_plugin.load() == j_direct.load() == [], "ژورنال خالی باید [] بدهد")
        A(jp.resolve_open_signals(Journal(jpath), {}, now=NOW, cfg=CFG)
          == resolve_open_signals(Journal(jpath), {}, now=NOW, cfg=CFG) == [],
          "resolve با ژورنال/دادهٔ خالی باید [] بدهد")
        A(same(jp.compute_stats([], NOW), compute_stats([], NOW)),
          "compute_stats خالی باید یکی باشد")

        # ── alerts: یک هشدار یک‌بارمصرفِ فعال‌شونده ──
        import src.app_paths as app_paths
        afile = Path(td) / "alerts.json"
        row = [{"id": "EURUSD|above|1.05", "symbol": "EURUSD", "dir": "above",
                "price": 1.05, "pip": 0.0001, "sticky": False,
                "created_at": "2026-09-01T00:00:00+00:00", "last_fired": None}]
        analyses = [SimpleNamespace(symbol="EURUSD", price=1.06)]
        from src.alerts import check_alerts
        ap = PriceAlertsPlugin()
        with mock.patch.object(app_paths, "data_dir", return_value=Path(td)):
            afile.write_text(json.dumps(row), encoding="utf-8")
            fired_plugin = ap.check_alerts(analyses, now=NOW)
            afile.write_text(json.dumps(row), encoding="utf-8")   # بازنشانی (یک‌بارمصرف)
            fired_direct = check_alerts(analyses, now=NOW)
            afile.write_text("[]", encoding="utf-8")
            fired_empty = ap.check_alerts(analyses, now=NOW)
        A(same(fired_plugin, fired_direct) and len(fired_direct) == 1
          and fired_direct[0]["_price"] == 1.06,
          "هشدار فعال‌شده باید در هر دو مسیر یکسان باشد")
        A(fired_empty == [], "بدون هشدار ثبت‌شده باید [] برگردد")


def test_report_dispatcher() -> None:
    from src.analysis.technical import analyze_symbol
    from src.fundamental.calendar import CalendarSnapshot
    from src.fundamental.news import NewsSnapshot
    from src.judge.scoring import Signal
    from src.journal.stats import compute_stats
    from src.report import console, fundamental, journal as rjournal, signal as rsignal

    rr = ReportRendererPlugin()
    st = compute_stats([], NOW)
    snap = _mk_snapshot()
    empty_snap = CalendarSnapshot(events=[], source="t")
    sig = Signal(
        symbol="EURUSD", fa_name="یورو به دلار آمریکا", direction="BUY",
        score=9, max_score=11, stars=4, entry=1.1000, sl=1.0950, tp=1.1100,
        pip=0.0001, atr=0.0012, risk_pips=50.0, reward_pips=100.0, rr=2.0,
        is_gold=False, session_fa="لندن + نیویورک", now=NOW,
        evidences=[], warnings=[], sl_capped=False, sid="test-1")
    analysis = analyze_symbol(CFG["symbols"][0], _mk_md("EURUSD", 1.10), CFG["analysis"])

    pairs = [
        ("no_signals_note", {"judgments": []},
         lambda p: rsignal.render_no_signals_note(**p)),
        ("judge_summary", {"judgments": [], "min_score": 7, "now": NOW},
         lambda p: rsignal.render_judge_summary(**p)),
        ("signal", {"s": sig, "include_footer": True},
         lambda p: rsignal.render_signal(**p)),
        ("veto", {"events": [], "symbol": "EURUSD", "now": NOW},
         lambda p: fundamental.render_veto(**p)),
        ("news", {"snap": NewsSnapshot()},
         lambda p: fundamental.render_news(**p)),
        ("calendar", {"snap": empty_snap, "symbols_cfg": [], "now": NOW},
         lambda p: fundamental.render_calendar(**p)),
        ("event_alert", {"event": snap.events[0], "symbols_cfg": [], "now": NOW},
         lambda p: fundamental.render_event_alert(**p)),
        ("briefing", {"analyses": [], "ranking": [], "cal_snap": None,
                      "news_snap": None, "symbols_cfg": [], "source_name": "—",
                      "now": NOW, "horizon_hours": 24.0},
         lambda p: fundamental.render_briefing(**p)),
        ("stats", {"stats": st, "open_entries": None, "now": NOW},
         lambda p: rjournal.render_stats(**p)),
        ("nightly", {"entries": [], "stats": st, "now": NOW},
         lambda p: rjournal.render_nightly(**p)),
        ("console", {"analyses": [], "ranking": [], "source_name": "—",
                     "tv_map": {}, "tv_tf": "4h", "cal_snap": None,
                     "news_snap": None, "symbols_cfg": [], "vetoes": {},
                     "cal_horizon": 48.0, "now": NOW, "judge_summary": "",
                     "simulated": False, "journal_line": ""},
         lambda p: console.render_report(**p)),
        ("symbol", {"a": analysis, "tv": None, "tv_tf": "4h",
                    "veto_events": None, "extra_lines": None, "now": NOW},
         lambda p: console.render_symbol(**p)),
        ("strength", {"ranking": [], "analyses": []},
         lambda p: console.render_strength(**p)),
    ]
    for kind, payload, direct in pairs:
        A(same(rr.render(kind, payload), direct(payload)),
          f"render({kind!r}) باید با فراخوانی مستقیم یکی باشد")

    A("card" in KINDS, "kind کارت اشتراک (دسکتاپ) باید ثبت باشد — بدون فراخوانی در CI")
    try:
        rr.render("no-such-kind", {})
        raise AssertionError("kind ناشناخته باید خطا بدهد")
    except ValueError as e:
        A("ناشناخته" in str(e), "پیام kind ناشناخته باید فارسی/پرسروصدا باشد")


# ══════════════════════════════════════════════════════════════
def main() -> int:
    tests = [test_registration, test_enable_disable, test_select_market_provider,
             test_golden_pure, test_judge_rule_plugins, test_judge_registry_parity,
             test_delegation_network,
             test_golden_journal_alerts, test_report_dispatcher]
    fails = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fails.append(f"{t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            fails.append(f"{t.__name__}: خطای غیرمنتظره {type(e).__name__}: {e}")
    if fails:
        print("❌ PLUGIN TESTS FAILED")
        for f in fails:
            print("  •", f)
        return 1
    print(f"✅ PLUGIN TESTS OK — {COUNT} بررسی پاس؛ هر adapter خروجیِ فراخوانی "
          f"مستقیم را عیناً بازتولید می‌کند (ثبت/فعال‌سازی/انتخاب منبع/خالص/"
          f"delegate/ژورنال+هشدار/رندر) + قواعد داور: ۱۵ rule-plugin و باتری "
          f"کامل سناریوها از مسیر registry بایت‌به‌بایت == طلایی")
    return 0


if __name__ == "__main__":
    sys.exit(main())
