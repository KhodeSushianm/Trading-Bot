# -*- coding: utf-8 -*-
"""موتور فاندامنتال و اخبار (مرحله ۲).

ماژول‌ها:
  calendar : تقویم اقتصادی (ForexFactory JSON) + تشخیص رویداد پراثر + دروازه وتو
  news     : رصد اخبار فارکس از فیدهای RSS رایگان با امتیازدهی جهت‌دار

هر دو ماژول «تحمل‌پذیر» هستند: اگر منبع از دسترس خارج شود، برنامه بدون آن‌ها
به کارش ادامه می‌دهد و فقط در گزارش ذکر می‌شود که داده فاندامنتال در دسترس نبود.
"""
from __future__ import annotations

from .calendar import (  # noqa: F401
    CalendarEvent,
    CalendarSnapshot,
    fetch_calendar,
    parse_events,
    upcoming_events,
    veto_for_symbol,
)
from .news import (  # noqa: F401
    NewsItem,
    NewsSnapshot,
    NewsVote,
    detect_currencies,
    fetch_news,
    market_movers,
    news_supports,
    parse_entries,
    score_text,
    subject_spans,
)
