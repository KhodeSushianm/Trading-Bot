# -*- coding: utf-8 -*-
"""لایهٔ رابط کاربری (UI) — تم مونوکروم تاریک، آیکون برداری، انیمیشن ظریف.

ماژول‌ها:
  theme   توکن‌های رنگ/تایپوگرافی/فاصله + تولید QSS
  icons   مجموعهٔ آیکون SVG خطی + رندرر کش‌شونده
  effects انیمیشن‌ها (fade، rise، نشانگر ناوبری، نقطهٔ تپنده)
  widgets ویجت‌های مشترک (Card، StatTile، StatusPill، NavRail، Toast)
  splash  صفحهٔ خوش‌آمدگویی
  dwm     اثرهای بومی ویندوز ۱۱ (نوار عنوان تیره، Mica، گوشه گرد)

قانون رنگ: همه‌چیز سیاه‌وسفید؛ فقط سبز (خرید/موفقیت) و قرمز (فروش/وتو/خطا).
"""
from __future__ import annotations

from .theme import DARK, Space, Theme, Type, build_qss  # noqa: F401  (re-export)
