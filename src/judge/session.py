# -*- coding: utf-8 -*-
"""سشن‌های بازار فارکس و وضعیت باز/بسته بودن بازار.

همهٔ ساعت‌ها UTC هستند.

⚠️ نکتهٔ صادقانه دربارهٔ ساعت تابستانی (DST):
سشن‌های لندن و نیویورک با تغییر ساعت تابستانی یک ساعت جابه‌جا می‌شوند.
محاسبهٔ دقیق DST نیاز به منطقهٔ زمانی هر کشور دارد؛ اینجا از بازهٔ
«میانه» استفاده شده که در بیشتر سال درست است و در بدترین حالت یک ساعت
زودتر/دیرتر تمام می‌شود. این فقط روی **۱ امتیاز از ۱۱** اثر دارد و
هیچ‌وقت باعث وتوی سیگنال نمی‌شود، پس ریسکش پذیرفتنی است.

بازار فارکس: جمعه ~۲۱:۰۰ UTC بسته و یکشنبه ~۲۲:۰۰ UTC (باز شدن سیدنی) باز می‌شود.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# نام سشن → (ساعت شروع، ساعت پایان) به UTC؛ پایان ≤ شروع یعنی از نیمه‌شب رد می‌شود
SESSIONS: dict[str, tuple[int, int]] = {
    "سیدنی": (21, 6),
    "توکیو": (0, 9),
    "لندن": (7, 16),
    "نیویورک": (12, 21),
}

# سشن‌هایی که برای جفت‌ارزهای ما نقدینگی خوبی دارند
_LIQUID = ("لندن", "نیویورک")

# بازهٔ هم‌پوشانی لندن و نیویورک — بهترین نقدینگی هفته
OVERLAP = (12, 16)

# بسته بودن بازار (UTC)
_FRIDAY_CLOSE_HOUR = 21      # جمعه از این ساعت به بعد
_SUNDAY_OPEN_HOUR = 22       # یکشنبه تا این ساعت بسته


@dataclass
class MarketStatus:
    """وضعیت بازار در یک لحظه."""

    open: bool
    reason_fa: str = ""
    sessions: tuple[str, ...] = ()
    overlap: bool = False
    liquid: bool = False

    @property
    def label(self) -> str:
        return session_label(self.sessions, self.overlap, self.open)


def sessions_of(now: datetime) -> tuple[str, ...]:
    """سشن‌های فعال در این لحظه."""
    h = now.hour + now.minute / 60.0
    active = []
    for name, (start, end) in SESSIONS.items():
        if start <= end:
            inside = start <= h < end
        else:                                   # از نیمه‌شب رد می‌شود (سیدنی)
            inside = h >= start or h < end
        if inside:
            active.append(name)
    return tuple(active)


def session_label(sessions: tuple[str, ...], overlap: bool = False,
                  is_open: bool = True) -> str:
    """برچسب فارسی سشن برای نمایش در گزارش."""
    if not is_open:
        return "بازار بسته 🔒"
    if not sessions:
        return "بین دو سشن (خلأ نقدینگی)"
    txt = " + ".join(sessions)
    return f"{txt} (هم‌پوشانی — بهترین نقدینگی ⭐)" if overlap else txt


def market_status(now: datetime) -> MarketStatus:
    """باز بودن بازار + سشن‌های فعال + هم‌پوشانی."""
    wd = now.weekday()          # 0=دوشنبه ... 4=جمعه 5=شنبه 6=یکشنبه
    h = now.hour

    if wd == 5:
        return MarketStatus(False, "شنبه — بازار فارکس بسته است 🔒")
    if wd == 6 and h < _SUNDAY_OPEN_HOUR:
        return MarketStatus(False, f"یکشنبه — بازار تا ساعت {_SUNDAY_OPEN_HOUR}:۰۰ UTC بسته است 🔒")
    if wd == 4 and h >= _FRIDAY_CLOSE_HOUR:
        return MarketStatus(False, f"جمعه شب — بازار از ساعت {_FRIDAY_CLOSE_HOUR}:۰۰ UTC بسته شد 🔒")

    sessions = sessions_of(now)
    overlap = OVERLAP[0] <= h < OVERLAP[1] and "لندن" in sessions and "نیویورک" in sessions
    liquid = any(s in _LIQUID for s in sessions)
    return MarketStatus(True, "", sessions, overlap, liquid)
