# -*- coding: utf-8 -*-
"""ابزار مشترک متن فارسی — ارقام، تاریخ و نام ماه‌ها.

یک منبع حقیقت برای همهٔ لایه‌ها (گزارش، داور، پنل) تا سبک نوشتن اعداد
بین بخش‌های مختلف برنامه یکی بماند.

قرارداد پروژه:
  • شمارش‌ها، امتیازها، پیپ و درصدها → ارقام فارسی (۰-۹)
  • **قیمت‌ها** → ارقام لاتین، چون کاربر آن‌ها را در متاتریدر تایپ می‌کند
    و کپی/پیست با ارقام فارسی خطا می‌دهد
  • نام اندیکاتورها (ADX=32، RSI=38) → لاتین، مطابق سبک گزارش تکنیکال
"""
from __future__ import annotations

from datetime import datetime

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

WEEKDAY_FA = {0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنجشنبه",
              4: "جمعه", 5: "شنبه", 6: "یکشنبه"}

MONTH_FA = {1: "ژانویه", 2: "فوریه", 3: "مارس", 4: "آوریل", 5: "مه", 6: "ژوئن",
            7: "ژوئیه", 8: "اوت", 9: "سپتامبر", 10: "اکتبر", 11: "نوامبر", 12: "دسامبر"}


def fa_num(v) -> str:
    """تبدیل ارقام به فارسی (رشته‌های ترکیبی مثل «+2» هم کار می‌کنند)."""
    return str(v).translate(FA_DIGITS)


def fa_date(dt: datetime, with_time: bool = True) -> str:
    """«شنبه ۱۹ سپتامبر ۲۰۲۶ — ۱۴:۳۰»"""
    s = f"{WEEKDAY_FA[dt.weekday()]} {fa_num(dt.day)} {MONTH_FA[dt.month]} {fa_num(dt.year)}"
    return f"{s} — {fa_num(f'{dt:%H:%M}')}" if with_time else s


def fa_ratio(n: float) -> str:
    """نسبت بدون صفر اعشار اضافی: ۲.۰ → «۲»، ۱.۵ → «۱٫۵»."""
    txt = f"{n:.1f}".rstrip("0").rstrip(".")
    return fa_num(txt.replace(".", "٫"))     # ممیز فارسی


def fa_pips(v: float, pip: float, is_gold: bool = False) -> str:
    """فاصلهٔ قیمت: برای طلا و فلزات با دلار، بقیه با پیپ."""
    if is_gold or pip >= 0.5:
        return f"{fa_num(f'{v:.0f}')} $"
    return f"{fa_num(f'{v / pip:.0f}')} پیپ"


def fa_countdown(minutes) -> str:
    """زمان باقی‌مانده تا رویداد به شکل خوانا (نه دقیقهٔ خام بزرگ).

    زیر ۱ ساعت → «۲۵ دقیقهٔ دیگر»
    زیر ۱ روز  → «۴ ساعت و ۱۲ دقیقهٔ دیگر»
    بیشتر      → «۲ روز دیگر»
    """
    m = abs(int(minutes))
    if m < 60:
        return f"{fa_num(m)} دقیقهٔ دیگر"
    if m < 24 * 60:
        h, mm = divmod(m, 60)
        if not mm:
            return f"{fa_num(h)} ساعت دیگر"
        return f"{fa_num(h)} ساعت و {fa_num(mm)} دقیقهٔ دیگر"
    return f"{fa_num(m // (24 * 60))} روز دیگر"
