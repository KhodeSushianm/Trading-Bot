# -*- coding: utf-8 -*-
"""پین‌های pipeline مرحله‌ای engine — فاز ۳b. آفلاین، بدون شبکه.

اجرا:  python tests/test_pipeline_switch.py     (از ریشهٔ ریپو)

طلاییِ engine (tests/test_engine_switch.py — ۴۷ بررسی) اثبات می‌کند خروجیِ
چرخهٔ کامل پس از رفتنِ بدنهٔ run_cycle روی PipelineRunner بایت‌به‌بایت
یکسان مانده. این فایل رفتارِ *افزودنیِ* جدید را پین می‌کند:

  • اجرای هر ۱۱ مرحلهٔ نام‌دار به ترتیب STAGES با رویدادهای stage.start/
    stage.done (payload مرحله/ok/unavailable/stop)
  • ترتیب نسبیِ ۱۲ رویداد استاندارد با رویدادهای مرحله (درهم‌بافتهٔ قطعی)
  • early-exit → StageResult(stop=True) در journal_pre: هیچ مرحلهٔ بعدی
    اجرا نمی‌شود و stage.done با stop=true منتشر می‌شود (همان «بازگشت
    زودهنگام» امروز — فقط نام‌دار و قابل رصد)
  • چرخهٔ سالم هیچ plugin.failed منتشر نمی‌کند
  • امضای عمومی run_cycle صددرصد ثابت (فاز ۳: امضاها فریز بودند)

حالت شبیه‌سازی (now_override) در هارنس طلایی فعال است → dispatch شاخهٔ
simulated می‌رود و signal.sent منتشر نمی‌کند (رفتار امروز — پین شد).
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
import tempfile
from datetime import datetime, timezone
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

# همهٔ رویدادهایی که engine منتشر می‌کند (۱۲ استاندارد + ۲ مرحله‌ای + خطا)
_ALL_EVENTS = (
    "cycle.start", "market.collected", "journal.resolved",
    "fundamental.collected", "vetoes.computed", "judge.done",
    "signal.created", "signal.sent", "alerts.fired", "report.rendered",
    "telegram.sent", "cycle.end", "news.breaking", "briefing.due",
    "journal.due", "plugin.registered", "plugin.failed", "plugin.disabled",
    "stage.start", "stage.done",
)


def _subscribe(engine, seen: list):
    """همهٔ رویدادها را به‌ترتیب وقوع در seen جمع می‌کند → فهرست unsubscribe."""
    offs = []

    def make(name):
        def handler(payload):
            if name == "stage.start":
                seen.append((name, (payload or {}).get("stage"), None))
            elif name == "stage.done":
                p = payload or {}
                seen.append((name, p.get("stage"), bool(p.get("stop"))))
            else:
                seen.append((name, None, None))
        return handler

    for ev in _ALL_EVENTS:
        offs.append(engine.BUS.on(ev, make(ev)))
    return offs


# ══════════════════════════════════════════════════════════════
def test_full_cycle_stage_events() -> None:
    """چرخهٔ کامل mock: ۱۱ مرحله به ترتیب + رویدادهای استاندارد درهم‌بافته."""
    from src import engine

    seen: list = []
    offs = _subscribe(engine, seen)
    try:
        with tempfile.TemporaryDirectory() as td:
            result, logs, sent = gen.run_mock_cycle(td)
    finally:
        for u in offs:
            u()

    A(result.get("ok") is True and len(result.get("signals") or []) == 1,
      "چرخهٔ mock سالم با ۱ سیگنال (پیش‌شرط سناریو)")

    expected = [
        ("cycle.start", None, None),
        ("stage.start", "collect_market", None),
        ("market.collected", None, None),
        ("stage.done", "collect_market", False),
        ("stage.start", "journal_pre", None),
        ("journal.resolved", None, None),
        ("stage.done", "journal_pre", False),
        ("stage.start", "collect_fundamental", None),
        ("fundamental.collected", None, None),
        ("stage.done", "collect_fundamental", False),
        ("stage.start", "compute_vetoes", None),
        ("vetoes.computed", None, None),
        ("stage.done", "compute_vetoes", False),
        ("stage.start", "judge", None),
        ("judge.done", None, None),
        ("signal.created", None, None),
        ("stage.done", "judge", False),
        ("stage.start", "render", None),
        ("report.rendered", None, None),
        ("stage.done", "render", False),
        ("stage.start", "dispatch_signals", None),
        # حالت شبیه‌سازی (now_override): dispatch شاخهٔ simulated است و
        # signal.sent منتشر نمی‌کند — همان رفتار امروزِ run_cycle
        ("stage.done", "dispatch_signals", False),
        ("stage.start", "price_alerts", None),
        ("alerts.fired", None, None),
        ("stage.done", "price_alerts", False),
        ("stage.start", "chart_cache", None),
        ("stage.done", "chart_cache", False),
        ("stage.start", "dashboard", None),
        ("stage.done", "dashboard", False),
        ("stage.start", "archive_notify", None),
        ("telegram.sent", None, None),
        ("cycle.end", None, None),
        ("stage.done", "archive_notify", False),
    ]
    if seen != expected:
        diffs = []
        for i in range(max(len(seen), len(expected))):
            a = seen[i] if i < len(seen) else "<نبود>"
            b = expected[i] if i < len(expected) else "<اضافه>"
            if a != b:
                diffs.append(f"  [{i}] اکنون {a} ≠ انتظار {b}")
        raise AssertionError("ترتیب رویدادهای pipeline فرق دارد:\n" + "\n".join(diffs[:10]))
    A(True, "۳۳ رویداد به ترتیب قطعی: ۱۱ مرحله (start/done) + ۱۱ رویداد استاندارد")
    A(not [s for s in seen if s[0] == "plugin.failed"],
      "چرخهٔ سالم هیچ plugin.failed منتشر نمی‌کند")
    stages_done = [s[1] for s in seen if s[0] == "stage.done"]
    from src.core.pipeline import STAGES
    A(stages_done == list(STAGES), "همهٔ ۱۱ مرحله به ترتیب STAGES اجرا شدند")


def test_early_exit_stops_pipeline() -> None:
    """early-exit امروز = stop در journal_pre: مراحل بعد هرگز اجرا نمی‌شوند."""
    from src import engine
    from src.data import yahoo_source
    import src.app_paths as app_paths

    seen: list = []
    offs = _subscribe(engine, seen)
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            d, l, c = tmp / "data", tmp / "logs", tmp / "cache"
            for x in (d, l, c):
                x.mkdir(parents=True, exist_ok=True)
            with mock.patch.object(app_paths, "data_dir", return_value=d), \
                 mock.patch.object(app_paths, "logs_dir", return_value=l), \
                 mock.patch.object(app_paths, "cache_dir", return_value=c), \
                 mock.patch.object(app_paths, "sent_alerts_path",
                                   return_value=c / "sent_alerts.json"), \
                 mock.patch.object(yahoo_source.YahooSource, "connect",
                                   lambda self: (_ for _ in ()).throw(RuntimeError("boom"))):
                result = engine.run_cycle(gen.make_cfg(), on_log=lambda m: None,
                                          now_override=NOW)
    finally:
        for u in offs:
            u()

    A(result["errors"] >= 1 and result["ok"] is False,
      "early-exit: errors ≥ 1 و ok=False (همان بازگشت امروز)")
    expected = [
        ("cycle.start", None, None),
        ("stage.start", "collect_market", None),
        ("market.collected", None, None),
        ("stage.done", "collect_market", False),
        ("stage.start", "journal_pre", None),
        ("journal.resolved", None, None),
        ("stage.done", "journal_pre", True),      # ← stop
    ]
    A(seen == expected,
      f"early-exit باید دقیقاً ۷ رویداد باشد با stop=true در journal_pre: {seen}")
    A(not [s for s in seen if s[0] == "stage.start"
           and s[1] in ("collect_fundamental", "judge", "render", "archive_notify")],
      "پس از stop هیچ مرحلهٔ بعدی شروع نشد")


def test_public_api_and_wiring() -> None:
    """امضای عمومی run_cycle ثابت + سیم‌کشی pipeline در engine."""
    from src import engine
    from src.core import pipeline as core_pipeline

    sig = inspect.signature(engine.run_cycle)
    A(list(sig.parameters) == ["cfg", "on_log", "now_override", "on_alert"],
      f"امضای run_cycle باید ثابت بماند: {list(sig.parameters)}")
    A(engine.STAGES is core_pipeline.STAGES
      and engine.PipelineRunner is core_pipeline.PipelineRunner
      and engine.StageResult is core_pipeline.StageResult,
      "engine از همان STAGES/PipelineRunner/StageResult هسته استفاده می‌کند")
    A(len(engine.STAGES) == 11, "۱۱ مرحلهٔ چرخه")


# ══════════════════════════════════════════════════════════════
def main() -> int:
    tests = [test_full_cycle_stage_events, test_early_exit_stops_pipeline,
             test_public_api_and_wiring]
    fails = []
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fails.append(f"{t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            fails.append(f"{t.__name__}: خطای غیرمنتظره {type(e).__name__}: {e}")
    if fails:
        print("❌ PIPELINE-SWITCH TESTS FAILED")
        for f in fails:
            print("  •", f)
        return 1
    print(f"✅ PIPELINE-SWITCH TESTS OK — {COUNT} بررسی پاس؛ run_cycle روی "
          f"PipelineRunner: ۱۱ مرحله به ترتیب قطعی با رویدادهای stage.*، "
          f"early-exit = stop در journal_pre، امضای عمومی ثابت")
    return 0


if __name__ == "__main__":
    sys.exit(main())
