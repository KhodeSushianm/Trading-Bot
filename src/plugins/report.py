# -*- coding: utf-8 -*-
"""پلاگین رندر گزارش‌ها — دیسپچر kind → توابع موجود report/* (فاز ۲).

قاعدهٔ adapter: `render(kind, payload)` فقط `fn(**payload)` است — قالب‌ها،
ایموجی‌ها، اعداد فارسی و ترتیب بخش‌ها همه در همان توابع فعلی‌اند.

⚠️ import همهٔ رندرها **تنبل** است (داخل _fn):
  ۱) ثبت پلاگین سبک بماند؛
  ۲) `card` (sharecard) در سطح ماژول PySide6 را می‌کشد که در CI نصب نیست —
     فقط وقتی واقعاً درخواست شود import می‌شود (دسکتاپ).

kind ناشناخته → ValueError فارسی (پرسروصدا؛ بی‌صدا رشتهٔ خالی برنمی‌گردانیم).
"""
from __future__ import annotations

from typing import Any, List, Tuple

from ..core.manifest import PluginManifest

KINDS = ("signal", "judge_summary", "no_signals_note", "calendar", "news",
         "event_alert", "veto", "briefing", "stats", "nightly", "console",
         "symbol", "strength", "card")


def _fn(kind: str) -> Any:
    if kind == "signal":
        from ..report.signal import render_signal as f
    elif kind == "judge_summary":
        from ..report.signal import render_judge_summary as f
    elif kind == "no_signals_note":
        from ..report.signal import render_no_signals_note as f
    elif kind == "calendar":
        from ..report.fundamental import render_calendar as f
    elif kind == "news":
        from ..report.fundamental import render_news as f
    elif kind == "event_alert":
        from ..report.fundamental import render_event_alert as f
    elif kind == "veto":
        from ..report.fundamental import render_veto as f
    elif kind == "briefing":
        from ..report.fundamental import render_briefing as f
    elif kind == "stats":
        from ..report.journal import render_stats as f
    elif kind == "nightly":
        from ..report.journal import render_nightly as f
    elif kind == "console":
        from ..report.console import render_report as f
    elif kind == "symbol":
        from ..report.console import render_symbol as f
    elif kind == "strength":
        from ..report.console import render_strength as f
    elif kind == "card":
        # دسکتاپ/Qt — عمداً تنبل (PySide6 در CI نصب نیست)
        from ..report.sharecard import render_card_pixmap as f
    else:
        raise ValueError(
            f"kind ناشناخته «{kind}» برای رندر گزارش — kinds معتبر: {', '.join(KINDS)}")
    return f


class ReportRendererPlugin:
    def render(self, kind: str, payload: dict) -> Any:
        return _fn(kind)(**(payload or {}))


def plugins() -> List[Tuple[PluginManifest, Any]]:
    return [
        (PluginManifest(
            id="report-renderer", version="1.0.0",
            provides=["odin.report@1"],
            config=None,
            platforms=["desktop", "android"],
            stage="render", priority=10, optional=True),
         lambda _ctx: ReportRendererPlugin()),
    ]
