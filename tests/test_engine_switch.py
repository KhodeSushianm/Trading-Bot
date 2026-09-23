# -*- coding: utf-8 -*-
"""میخ‌های رفتاری engine — فاز ۳ (سوییچ به registry). آفلاین، بدون شبکه.

اجرا:  python tests/test_engine_switch.py     (از ریشهٔ ریپو)

انضباط «اول میخ، بعد چکش»:
  • این تست‌ها ابتدا روی engine *فعلی* نوشته و سبز شده‌اند (کامیت تست).
  • سپس سوییچ فاز ۳ انجام می‌شود و **همین تست‌ها بدون هیچ تغییری** باید
    سبز بمانند — اثبات اینکه خروجی/لاگ‌ها/امضاها عوض نشده‌اند.
  • تنها بخش مشروط: رویدادهای bus (قبل از سوییچ skip، بعد از سوییچ فعال) —
    چون bus رفتاری *افزودنی* بدون listener است.

طلاییِ چرخهٔ کامل: tests/golden/run_cycle_golden.json (با
tests/golden/gen_engine_golden.py ضبط شده — دادهٔ ساختگی قطعی، now_override
ثابت، تلگرام mock). مقایسه شامل result نرمال‌شده + همهٔ خطوط لاگ + فهرست
ارسال‌های تلگرام است.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

COUNT = 0


def A(cond: bool, msg: str) -> None:
    global COUNT
    assert cond, msg
    COUNT += 1


# ── بارگذاری هارنس طلایی (بدون اجرای main آن) ─────────────────
_spec = importlib.util.spec_from_file_location(
    "gen_engine_golden", HERE / "golden" / "gen_engine_golden.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

NOW = gen.NOW


def _tmp_dirs(tmp: Path):
    d, l, c = tmp / "data", tmp / "logs", tmp / "cache"
    for x in (d, l, c):
        x.mkdir(parents=True, exist_ok=True)
    return d, l, c


def _patch_paths(st, tmp: Path):
    import src.app_paths as app_paths
    d, l, c = _tmp_dirs(tmp)
    st.enter_context(mock.patch.object(app_paths, "data_dir", return_value=d))
    st.enter_context(mock.patch.object(app_paths, "logs_dir", return_value=l))
    st.enter_context(mock.patch.object(app_paths, "cache_dir", return_value=c))
    st.enter_context(mock.patch.object(app_paths, "sent_alerts_path",
                                       return_value=c / "sent_alerts.json"))
    return d, l, c


# ══════════════════════════════════════════════════════════════
def test_golden_cycle() -> None:
    """چرخهٔ کامل mock == فایل طلایی (result + logs + telegram sends)."""
    golden_path = HERE / "golden" / "run_cycle_golden.json"
    A(golden_path.exists(),
      "فایل طلایی وجود ندارد — اول python tests/golden/gen_engine_golden.py")
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        result, logs, sent = gen.run_mock_cycle(td)
    got = {"result": gen.normalize_result(result),
           "logs": gen.normalize_logs(logs),
           "sent_messages": sent}
    if got != golden:
        # تفاوت را قابل‌تشخیص کن (کمک به دیباگ)
        diffs = []
        if got["logs"] != golden["logs"]:
            gl, el = got["logs"], golden["logs"]
            for i in range(max(len(gl), len(el))):
                a = gl[i] if i < len(gl) else "<نبود>"
                b = el[i] if i < len(el) else "<نبود>"
                if a != b:
                    diffs.append(f"  log[{i}]: اکنون «{a[:80]}» ≠ طلایی «{b[:80]}»")
        if got["result"] != golden["result"]:
            for k in sorted(set(got["result"]) | set(golden["result"])):
                if got["result"].get(k) != golden["result"].get(k):
                    diffs.append(f"  result[{k}] تغییر کرد")
        if got["sent_messages"] != golden["sent_messages"]:
            diffs.append(f"  sent_messages: {got['sent_messages']} ≠ {golden['sent_messages']}")
        raise AssertionError("چرخه با طلایی فرق دارد:\n" + "\n".join(diffs[:14]))
    A(True, "چرخهٔ کامل mock == طلایی")
    A(len(got["result"]["signals"]) == 1, "طلایی باید دقیقاً ۱ سیگنال داشته باشد")


def test_early_exit() -> None:
    """قطع منبع داده → لاگ‌های فارسیِ دقیق + errors=1 + بازگشت زودهنگام."""
    from src import engine
    from src.data import yahoo_source
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with contextlib.ExitStack() as st:
            _patch_paths(st, tmp)
            st.enter_context(mock.patch.object(
                yahoo_source.YahooSource, "connect",
                lambda self: (_ for _ in ()).throw(RuntimeError("boom"))))
            logs: list = []
            res = engine.run_cycle(gen.make_cfg(), on_log=logs.append, now_override=NOW)
    clean = gen.normalize_logs(logs)
    A(res["ok"] is False and res["errors"] == 1, "قطع داده → ok=False, errors=1")
    A("❌ اتصال به منبع داده ناموفق: boom" in clean,
      f"لاگ دقیق اتصال ناموفق گم شد: {clean[:4]}")
    A(res["signals"] == [], "در مسیر زودهنگام سیگنالی نداریم")
    A("resolved" in res and res["resolved"] == [],
      "journal_pre باید قبل از بازگشت زودهنگام اجرا شود (resolved=[])")

    # شاخهٔ دوم: اتصال سالم ولی fetch برای همه None → «هیچ نمادی تحلیل نشد»
    with tempfile.TemporaryDirectory() as td:
        with contextlib.ExitStack() as st:
            _patch_paths(st, Path(td))
            st.enter_context(mock.patch.object(yahoo_source.YahooSource, "connect",
                                               lambda self: None))
            st.enter_context(mock.patch.object(yahoo_source.YahooSource, "disconnect",
                                               lambda self: None))
            st.enter_context(mock.patch.object(yahoo_source.YahooSource, "fetch",
                                               lambda self, sym_cfg: None))
            logs2: list = []
            res2 = engine.run_cycle(gen.make_cfg(), on_log=logs2.append, now_override=NOW)
    clean2 = gen.normalize_logs(logs2)
    A(res2["ok"] is False and res2["errors"] >= 1, "fetch=None برای همه → ok=False")
    A("❌ هیچ نمادی تحلیل نشد — اینترنت/تنظیمات را بررسی کنید" in clean2,
      "لاگ دقیق «هیچ نمادی تحلیل نشد» گم شد")


def test_send_telegram_paths() -> None:
    """سه مسیر _send_telegram — پیام‌ها و مقادیر بازگشتی دقیق."""
    from src import engine
    cfg_off = gen.make_cfg()
    cfg_off["telegram"] = {}
    logs: list = []
    ok, msg = engine._send_telegram(cfg_off, "متن", logs.append)
    A((ok, msg) == (False, "تنظیم نشده"), "تلگرام تنظیم‌نشده → (False, 'تنظیم نشده')")
    A(logs and logs[-1] == "[i] تلگرام تنظیم نشده — گزارش فقط در پنل/کنسول نمایش داده می‌شود",
      f"لاگ دقیق تنظیم‌نشده: {logs[-1] if logs else None}")

    cfg_on = gen.make_cfg()
    with mock.patch("src.notify.telegram.send_message", return_value=(True, "OK")):
        logs2: list = []
        ok2, msg2 = engine._send_telegram(cfg_on, "متن", logs2.append,
                                          label="🎯 سیگنال EURUSD")
    A((ok2, msg2) == (True, "OK"), "مسیر موفق → (True, 'OK')")
    A(logs2[0] == "📱 ارسال 🎯 سیگنال EURUSD به تلگرام...", f"لاگ ارسال: {logs2[0]}")
    A(logs2[1] == "✅ تلگرام: OK", f"لاگ نتیجه: {logs2[1]}")

    with mock.patch("src.notify.telegram.send_message", return_value=(False, "403")):
        logs3: list = []
        ok3, msg3 = engine._send_telegram(cfg_on, "متن", logs3.append)
    A((ok3, msg3) == (False, "403"), "مسیر شکست → (False, '403')")
    A(logs3[-1] == "❌ تلگرام: 403", f"لاگ شکست: {logs3[-1]}")


def test_names_contract() -> None:
    """نام‌های سطح ماژول که panel/main/تست‌های دستی به آن‌ها تکیه دارند."""
    from src import engine
    for name in ("run_cycle", "run_briefing", "check_event_alerts",
                 "run_journal_report", "should_send_signal", "journal_signal",
                 "BotLoop", "_send_telegram", "_collect_market",
                 "_collect_fundamental", "_compute_vetoes", "_archive",
                 "_load_signal_state", "_save_signal_state", "datetime"):
        A(hasattr(engine, name), f"نام «{name}» باید در سطح ماژول engine بماند")


def test_check_event_alerts_dry() -> None:
    """هشدار رویداد پراثر — مسیر dry_run (بدون تلگرام/فایل)."""
    from src import engine
    from src.fundamental.calendar import CalendarEvent, CalendarSnapshot
    ev = CalendarEvent(when=NOW + timedelta(minutes=20), country="USD",
                       title="Non-Farm Payrolls", title_fa="اشتغال غیرکشاورزی",
                       impact="HIGH", forecast="185K", previous="175K",
                       category="اشتغال و بازار کار", polarity=1, source="t")
    snap = CalendarSnapshot(events=[ev], fetched_at=NOW, source="t", fetched=True)
    with tempfile.TemporaryDirectory() as td:
        with contextlib.ExitStack() as st:
            _patch_paths(st, Path(td))
            logs: list = []
            fired = engine.check_event_alerts(gen.make_cfg(), cal_snap=snap,
                                              on_log=logs.append, now=NOW,
                                              dry_run=True)
    A(len(fired) == 1 and fired[0]["sent"] is False, "یک رویداد، dry_run → sent=False")
    A(fired[0]["minutes"] == 20, "دقیقهٔ باقی‌مانده باید ۲۰ باشد")
    A(any("🚨 هشدار رویداد" in ln and "[پیش‌نمایش — ارسال نشد]" in ln for ln in logs),
      "لاگ فارسی هشدار (پیش‌نمایش) باید باشد")


def test_briefing_and_journal_report() -> None:
    """بریفینگ با قطع داده → بازگشت زودهنگام؛ کارنامه با ژورنال خالی."""
    from src import engine
    from src.data import yahoo_source
    with tempfile.TemporaryDirectory() as td:
        with contextlib.ExitStack() as st:
            _patch_paths(st, Path(td))
            st.enter_context(mock.patch.object(
                yahoo_source.YahooSource, "connect",
                lambda self: (_ for _ in ()).throw(RuntimeError("boom"))))
            logs: list = []
            res = engine.run_briefing(gen.make_cfg(), on_log=logs.append)
    A(res["ok"] is False and res["errors"] >= 1, "بریفینگ با قطع داده → ok=False")
    A("❌ بریفینگ ساخته نشد — دادهٔ بازار در دسترس نیست" in gen.normalize_logs(logs),
      "لاگ دقیق بریفینگ ناموفق")

    cfg_off = gen.make_cfg()
    cfg_off["telegram"] = {}
    with tempfile.TemporaryDirectory() as td:
        with contextlib.ExitStack() as st:
            _patch_paths(st, Path(td))
            res2 = engine.run_journal_report(cfg_off, on_log=lambda m: None,
                                             kind="stats")
    A(res2["ok"] is True and res2["stats"].total == 0, "کارنامهٔ ژورنال خالی → ok, total=0")
    A(res2["telegram"] == (False, "تنظیم نشده"), "کارنامه بدون تلگرام → تنظیم نشده")


def test_journal_signal_and_state() -> None:
    """journal_signal فایل ژورنال را append می‌کند؛ state سیگنال رفت‌وبرگشت."""
    from src import engine
    from src.judge.scoring import Signal
    sig = Signal(symbol="EURUSD", fa_name="یورو به دلار آمریکا", direction="BUY",
                 score=9, max_score=11, stars=4, entry=1.1000, sl=1.0950,
                 tp=1.1100, pip=0.0001, atr=0.0012, risk_pips=50.0,
                 reward_pips=100.0, rr=2.0, is_gold=False,
                 session_fa="لندن + نیویورک", now=NOW, sid="pin-1")
    with tempfile.TemporaryDirectory() as td:
        with contextlib.ExitStack() as st:
            _d, logs_dir, cache_dir = _patch_paths(st, Path(td))
            engine.journal_signal(sig, sent=True)
            jf = logs_dir / "signals.jsonl"
            A(jf.exists() and len(jf.read_text(encoding="utf-8").splitlines()) == 1,
              "journal_signal باید یک خط در signals.jsonl بنویسد")
            rec = json.loads(jf.read_text(encoding="utf-8").strip())
            A(rec["id"] == "pin-1" and rec["sent"] is True and rec["symbol"] == "EURUSD",
              "رکورد ژورنال باید دقیق باشد")

            state = {"EURUSD|BUY": {"ts": (NOW - timedelta(minutes=30)).isoformat(),
                                    "score": 7}}
            go, why = engine.should_send_signal(state, sig, {"resend_cooldown_minutes": 180,
                                                             "resend_score_gain": 2}, now=NOW)
            A(go is True and "بهتر" in why,
              "امتیاز ۹ در برابر ۷ (delta=2 ≥ gain) → ارسال با دلیل «بهتر شد»")
            state2 = {"EURUSD|BUY": {"ts": (NOW - timedelta(minutes=30)).isoformat(),
                                     "score": 9}}
            go2, why2 = engine.should_send_signal(state2, sig, {"resend_cooldown_minutes": 180,
                                                                "resend_score_gain": 2}, now=NOW)
            A(go2 is False and "دقیقه پیش" in why2, "تکراری در cooldown → ارسال نشود")

            engine._save_signal_state({"GBPUSD|SELL": {
                "ts": datetime.now(timezone.utc).isoformat(), "score": 7}})
            loaded = engine._load_signal_state()
            A("GBPUSD|SELL" in loaded, "state رفت‌وبرگشت باید سالم باشد")
            A((cache_dir / "sent_signals.json").exists(), "فایل state در cache_dir نوشته شود")


def test_bus_events_when_present() -> None:
    """بعد از سوییچ فاز ۳: رویدادهای استاندارد باید منتشر شوند (افزودنی)."""
    from src import engine
    if not hasattr(engine, "BUS"):
        A(True, "engine.BUS هنوز نیست (قبل از سوییچ) — skip عمدی")
        return
    from src.data import yahoo_source
    seen: list = []
    off = engine.BUS.on("cycle.start", lambda p: seen.append("cycle.start"))
    off2 = engine.BUS.on("market.collected", lambda p: seen.append("market.collected"))
    off3 = engine.BUS.on("journal.resolved", lambda p: seen.append("journal.resolved"))
    off4 = engine.BUS.on("cycle.end", lambda p: seen.append("cycle.end"))
    try:
        with tempfile.TemporaryDirectory() as td:
            with contextlib.ExitStack() as st:
                _patch_paths(st, Path(td))
                st.enter_context(mock.patch.object(
                    yahoo_source.YahooSource, "connect",
                    lambda self: (_ for _ in ()).throw(RuntimeError("boom"))))
                engine.run_cycle(gen.make_cfg(), on_log=lambda m: None, now_override=NOW)
    finally:
        for u in (off, off2, off3, off4):
            u()
    A("cycle.start" in seen, "رویداد cycle.start باید منتشر شود")
    A("market.collected" in seen, "رویداد market.collected باید منتشر شود")
    A("journal.resolved" in seen, "رویداد journal.resolved باید منتشر شود")


# ══════════════════════════════════════════════════════════════
def main() -> int:
    tests = [test_golden_cycle, test_early_exit, test_send_telegram_paths,
             test_names_contract, test_check_event_alerts_dry,
             test_briefing_and_journal_report, test_journal_signal_and_state,
             test_bus_events_when_present]
    fails = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fails.append(f"{t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            fails.append(f"{t.__name__}: خطای غیرمنتظره {type(e).__name__}: {e}")
    if fails:
        print("❌ ENGINE-SWITCH TESTS FAILED")
        for f in fails:
            print("  •", f)
        return 1
    print(f"✅ ENGINE-SWITCH TESTS OK — {COUNT} بررسی پاس؛ میخ‌های رفتاری engine "
          f"(طلایی چرخهٔ کامل + early-exit + تلگرام + نام‌ها + هشدار رویداد + "
          f"بریفینگ/کارنامه + ژورنال/state) سبز‌اند")
    return 0


if __name__ == "__main__":
    sys.exit(main())
