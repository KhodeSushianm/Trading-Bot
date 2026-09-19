# -*- coding: utf-8 -*-
"""سنجش قدرت ارزها (Currency Strength Meter).

روش: درصد تغییر قیمت هر نماد در N کندل یک‌ساعته اخیر محاسبه می‌شود؛
برای ارز پایه با علامت + و برای ارز مظنه با علامت − ثبت و سپس
برای هر ارز میانگین گرفته می‌شود. خروجی: رتبه‌بندی قوی‌ترین تا ضعیف‌ترین.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from ..data.base import MarketData


def currency_strength(datasets: Dict[str, MarketData],
                      lookback_h1: int = 24) -> List[Tuple[str, float]]:
    """رتبه‌بندی قدرت ارزها بر اساس داده H1.

    Args:
        datasets: نگاشت نام نماد → MarketData
        lookback_h1: تعداد کندل یک‌ساعته برای محاسبه تغییر (پیش‌فرض ۲۴ ≈ یک روز)

    Returns:
        فهرست (ارز، درصد تغییر میانگین) — مرتب از قوی به ضعیف
    """
    changes: Dict[str, List[float]] = {}
    for name, md in datasets.items():
        close = md.h1["Close"]
        if len(close) <= lookback_h1:
            continue
        pct = (float(close.iloc[-1]) / float(close.iloc[-1 - lookback_h1]) - 1) * 100
        # نام نماد ممکن است با config یکی باشد؛ base/quote از خود داده قابل استخراج نیست،
        # پس از قرارداد نام‌گذاری جفت‌ارزها استفاده می‌کنیم: BASEQUOTE (۶ کاراکتر) یا XAUUSD
        base, quote = _split_symbol(name)
        if base is None:
            continue
        changes.setdefault(base, []).append(pct)
        changes.setdefault(quote, []).append(-pct)

    avg = {c: float(np.mean(v)) for c, v in changes.items()}
    return sorted(avg.items(), key=lambda x: -x[1])


def _split_symbol(name: str) -> Tuple[str | None, str | None]:
    """جدا کردن ارز پایه و مظنه از نام نماد (مثل EURUSD یا XAUUSD)."""
    clean = name.replace("=X", "").upper()
    if len(clean) == 6:
        return clean[:3], clean[3:]
    return None, None
