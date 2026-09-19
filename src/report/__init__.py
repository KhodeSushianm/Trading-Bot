# -*- coding: utf-8 -*-
"""لایهٔ گزارش‌نویسی فارسی.

  console     — گزارش دورهٔ تحلیل (تکنیکال + تاییدیه TV + تقویم + اخبار)
  fundamental — بخش‌های تقویم اقتصادی/اخبار، بریفینگ صبحگاهی و هشدار رویداد
  signal      — پیام سیگنال با دلایل کامل + خلاصهٔ داوری همهٔ نمادها
"""
from __future__ import annotations

from .console import render_report, render_strength, render_symbol  # noqa: F401
from .fundamental import (  # noqa: F401
    render_briefing,
    render_calendar,
    render_event_alert,
    render_news,
)
from .signal import (  # noqa: F401
    fmt_price,
    render_judge_summary,
    render_no_signals_note,
    render_signal,
)
