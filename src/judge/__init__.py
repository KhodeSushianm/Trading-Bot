# -*- coding: utf-8 -*-
"""داور امتیازدهی (Confluence Judge) — مرحله ۳.

  session  : سشن‌های بازار، باز/بسته بودن، زمان‌بندی مناسب
  scoring  : جدول امتیاز، دروازه‌های وتو، محاسبهٔ ورود/حد ضرر/هدف

خروجی نهایی یک `Judgment` برای هر نماد است: یا یک `Signal` کامل با دلایل،
یا دلیل صادقانهٔ رد شدن (وتو / امتیاز ناکافی / ستاپ نبود).
"""
from __future__ import annotations

from .scoring import (  # noqa: F401
    Evidence,
    Judgment,
    Signal,
    Veto,
    judge_symbol,
    judge_all,
)
from .session import market_status, session_label, sessions_of  # noqa: F401
