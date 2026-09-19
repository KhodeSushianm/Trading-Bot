# -*- coding: utf-8 -*-
"""اندیکاتورهای تکنیکال — پیاده‌سازی خالص با pandas/numpy (بدون وابستگی اضافه).

همه توابع یک Series یا DataFrame با ایندکس زمانی می‌گیرند و Series برمی‌گردانند.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(close: pd.Series, period: int) -> pd.Series:
    """میانگین متحرک نمایی."""
    return close.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """شاخص قدرت نسبی (Wilder)."""
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def true_range(df: pd.DataFrame) -> pd.Series:
    """دامنه واقعی (True Range)."""
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    return pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """میانگین دامنه واقعی (Wilder) — معیار نوسان‌پذیری."""
    return true_range(df).ewm(alpha=1 / period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """شاخص میانگین جهت‌دار — قدرت روند (بدون جهت)."""
    h, l = df["High"], df["Low"]
    up, dn = h.diff(), -l.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = true_range(df).ewm(alpha=1 / period, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / a.replace(0, np.nan)
    mdi = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / a.replace(0, np.nan)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0)


def swing_levels(df: pd.DataFrame, window: int = 5) -> tuple[list[float], list[float]]:
    """قله‌ها و کف‌های چرخشی (swing) برای یافتن سطوح حمایت/مقاومت.

    Returns: (لیست کف‌ها, لیست قله‌ها)
    """
    highs = df["High"].to_numpy()
    lows = df["Low"].to_numpy()
    peak_highs: list[float] = []
    peak_lows: list[float] = []
    for i in range(window, len(df) - window):
        if highs[i] == highs[i - window:i + window + 1].max():
            peak_highs.append(float(highs[i]))
        if lows[i] == lows[i - window:i + window + 1].min():
            peak_lows.append(float(lows[i]))
    return peak_lows, peak_highs


def nearest_levels(price: float, df: pd.DataFrame, window: int = 5) -> tuple[float | None, float | None]:
    """نزدیک‌ترین حمایت (زیر قیمت) و مقاومت (بالای قیمت) از swing های تایم‌فریم.

    Returns: (support, resistance) — هرکدام ممکن است None باشد
    """
    lows, highs = swing_levels(df, window)
    support = max((x for x in lows if x < price), default=None)
    resistance = min((x for x in highs if x > price), default=None)
    return support, resistance
