# -*- coding: utf-8 -*-
"""ژورنال سیگنال — مرحله ۴.

  store    نگهداری append-only رکوردها (event-sourcing؛ هرگز بازنویسی نمی‌شود)
  tracker  تعیین خودکار نتیجهٔ سیگنال‌های باز (TP / SL / EXPIRED) از روی کندل‌ها
  stats    آمار دقت: کلی، هفتگی، به تفکیک نماد/جهت/امتیاز/مدرک

چرا append-only؟
  فایل ژورنال تنها سند صداقت سیستم است. اگر وسط نوشتن برق برود یا برنامه
  کرش کند، بازنویسیِ فایل می‌توانست تاریخچه را نابود کند. پس نتیجهٔ هر سیگنال
  به‌صورت رکورد جداگانهٔ ``kind="outcome"`` با همان ``id`` الحاق می‌شود و
  وضعیت نهایی با replay ساخته می‌شود.
"""
from __future__ import annotations

from .stats import Stats, compute_stats  # noqa: F401
from .store import Entry, Journal  # noqa: F401
from .tracker import resolve_open_signals  # noqa: F401
