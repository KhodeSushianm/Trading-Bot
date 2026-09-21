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

# ══════════════════════════════════════════════════════════════
#  وقت تهران + تاریخ جلالی (v0.19.0 — پورت دقیق fa.js اندروید)
#  منطق داخلی موتور UTC می‌ماند؛ این‌ها فقط لایهٔ نمایش‌اند.
#  ایران از ۱۴۰۱ ساعت تابستانی ندارد → اختلاف ثابت +۳:۳۰.
# ══════════════════════════════════════════════════════════════
from datetime import timedelta, timezone

TEH_MIN = 210

J_MONTH_FA = {
    1: "فروردین", 2: "اردیبهشت", 3: "خرداد", 4: "تیر", 5: "مرداد", 6: "شهریور",
    7: "مهر", 8: "آبان", 9: "آذر", 10: "دی", 11: "بهمن", 12: "اسفند",
}
_J_BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
             1635, 2060, 2097, 2192, 2262, 2324, 2394, 3178]


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def tehran(dt: datetime) -> datetime:
    return _as_utc(dt) + timedelta(minutes=TEH_MIN)


def hhmm(dt: datetime) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def hhmm_teh(dt: datetime) -> str:
    return hhmm(tehran(dt))


def py_weekday_teh(dt: datetime) -> int:
    """weekday قرارداد پایتون/پروژه: 0=دوشنبه … 6=یکشنبه (به وقت تهران)."""
    return tehran(dt).weekday()


def fa_date_teh(dt: datetime, with_time: bool = True) -> str:
    t = tehran(dt)
    s = f"{WEEKDAY_FA[t.weekday()]} {fa_num(t.day)} {MONTH_FA[t.month]} {fa_num(t.year)}"
    if not with_time:
        return s
    return s + " — " + fa_num(hhmm(t))


def day_key_teh(dt: datetime) -> str:
    t = tehran(dt)
    return f"{t.year:04d}-{t.month:02d}-{t.day:02d}"


def _jdiv(a: int, b: int) -> int:
    """همان ~~(a/b) در fa.js — trunc به سمت صفر (نه floor). برای مقادیر
    منفیِ میانیِ الگوریتم جلالی حیاتی است. بازهٔ ورودی‌ها << 2^53."""
    return int(a / b)


def _jmod(a: int, b: int) -> int:
    return a - _jdiv(a, b) * b


def _g2d(gy: int, gm: int, gd: int) -> int:
    d = (_jdiv((gy + _jdiv(gm - 8, 6) + 100100) * 1461, 4)
         + _jdiv(153 * _jmod(gm + 9, 12) + 2, 5) + gd - 34840408)
    d = d - _jdiv(_jdiv(gy + 100100 + _jdiv(gm - 8, 6), 100) * 3, 4) + 752
    return d


def _d2g(jdn: int) -> tuple:
    j = 4 * jdn + 139361631
    j = j + _jdiv(_jdiv(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = _jdiv(_jmod(j, 1461), 4) * 5 + 308
    gd = _jdiv(_jmod(i, 153), 5) + 1
    gm = _jmod(_jdiv(i, 153), 12) + 1
    gy = _jdiv(j, 1461) - 100100 + _jdiv(8 - gm, 6)
    return gy, gm, gd


def _jal_cal(jy: int) -> tuple:
    bl = len(_J_BREAKS)
    gy = jy + 621
    leap_j = -14
    jp = _J_BREAKS[0]
    jm = 0
    jump = 0
    i = 1
    while i < bl:
        jm = _J_BREAKS[i]
        jump = jm - jp
        if jy < jm:
            break
        leap_j = leap_j + _jdiv(jump, 33) * 8 + _jdiv(_jmod(jump, 33), 4)
        jp = jm
        i += 1
    n = jy - jp
    leap_j = leap_j + _jdiv(n, 33) * 8 + _jdiv(_jmod(n, 33) + 3, 4)
    if _jmod(jump, 33) == 4 and jump - n == 4:
        leap_j += 1
    leap_g = _jdiv(gy, 4) - _jdiv((_jdiv(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + _jdiv(jump + 4, 33) * 33
    leap = _jmod(_jmod(n + 1, 33) - 1, 4)
    if leap == -1:
        leap = 4
    return leap, gy, march


def _d2j(jdn: int) -> tuple:
    gy = _d2g(jdn)[0]
    jy = gy - 621
    _, _, march = _jal_cal(jy)
    jdn1f = _g2d(gy, 3, march)
    k = jdn - jdn1f
    if k >= 0:
        if k <= 185:
            return jy, 1 + _jdiv(k, 31), _jmod(k, 31) + 1
        k -= 186
    else:
        jy -= 1
        k += 179
        leap, _, _ = _jal_cal(jy)
        if leap == 1:
            k += 1
    return jy, 7 + _jdiv(k, 30), _jmod(k, 30) + 1


def to_jalali_teh(dt: datetime) -> tuple:
    t = tehran(dt)
    return _d2j(_g2d(t.year, t.month, t.day))


def jalali_fa(dt: datetime) -> str:
    """«شنبه ۲۸ شهریور ۱۴۰۵» — به وقت تهران (مثل jalaliFa در fa.js)."""
    jy, jm, jd = to_jalali_teh(dt)
    return f"{WEEKDAY_FA[py_weekday_teh(dt)]} {fa_num(jd)} {J_MONTH_FA[jm]} {fa_num(jy)}"
