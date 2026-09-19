# -*- coding: utf-8 -*-
"""لایهٔ گزارش‌نویسی فارسی.

  console     — گزارش دورهٔ تحلیل (تکنیکال + تاییدیه TV + تقویم + اخبار)
  fundamental — بخش‌های تقویم اقتصادی/اخبار، بریفینگ صبحگاهی و هشدار رویداد
"""
from __future__ import annotations

from .console import render_report, render_strength, render_symbol  # noqa: F401
from .fundamental import (  # noqa: F401
    render_briefing,
    render_calendar,
    render_event_alert,
    render_news,
)
