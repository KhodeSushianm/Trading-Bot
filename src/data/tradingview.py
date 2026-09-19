# -*- coding: utf-8 -*-
"""تاییدیه متقابل از TradingView — API غیررسمی (بدون لاگین) با کتابخانه tradingview-ta.

چه چیزی می‌دهد: قیمت لحظه‌ای + اندیکاتورهای محاسبه‌شده توسط خود تریدینگ‌ویو
+ «امتیاز تکنیکال» رسمی آن (توصیه خرید/فروش بر اساس ده‌ها اندیکاتور).

کاربرد: مدرک تاییدی متقابل در گزارش (و در مرحله ۳: امتیاز اضافی در داور).

⚠️ نکته صادقانه: این دسترسی غیررسمی است و ممکن است با تغییرات تریدینگ‌ویو
قطع شود؛ به همین دلیل برنامه هرگز به آن وابسته نیست و در صورت خطا،
بی‌سروصدا رد می‌شود (بقیه گزارش کار می‌کند).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

# نگاشت مقدار config به رشته فاصله‌زمانی کتابخانه
_INTERVALS = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1D", "1w": "1W"}


@dataclass
class TVSnapshot:
    """نتیجه تاییدیه تریدینگ‌ویو برای یک نماد."""
    symbol: str
    close: float | None
    rsi: float | None
    adx: float | None
    recommendation: str          # STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL
    buy: int = 0
    sell: int = 0
    neutral: int = 0
    timeframe: str = "4h"


def fetch_tv_snapshot(symbols_cfg: List[dict], timeframe: str = "4h",
                      timeout: int = 8) -> Dict[str, TVSnapshot]:
    """گرفتن تاییدیه تریدینگ‌ویو برای همه نمادها. در صورت نبود کتابخانه یا خطا، {} برمی‌گرداند."""
    try:
        from tradingview_ta import TA_Handler
    except ImportError:
        print("[!] کتابخانه tradingview-ta نصب نیست — تاییدیه تریدینگ‌ویو رد شد "
              "(نصب: pip install tradingview-ta)")
        return {}

    tf = _INTERVALS.get(str(timeframe).lower(), "4h")
    out: Dict[str, TVSnapshot] = {}
    for sym in symbols_cfg:
        tv = sym.get("tv") or {}
        if not tv.get("symbol"):
            continue
        try:
            handler = TA_Handler(
                screener=tv.get("screener", "forex"),
                exchange=tv.get("exchange", "FX"),
                symbol=tv["symbol"],
                interval=tf,
                timeout=timeout,
            )
            a = handler.get_analysis()
            ind = a.indicators or {}
            summary = a.summary or {}
            out[sym["name"]] = TVSnapshot(
                symbol=sym["name"],
                close=ind.get("close"),
                rsi=ind.get("RSI"),
                adx=ind.get("ADX"),
                recommendation=str(summary.get("RECOMMENDATION", "NEUTRAL")).upper(),
                buy=int(summary.get("BUY", 0)),
                sell=int(summary.get("SELL", 0)),
                neutral=int(summary.get("NEUTRAL", 0)),
                timeframe=tf,
            )
        except Exception as e:
            print(f"[!] تاییدیه تریدینگ‌ویو برای {sym['name']} ناموفق بود: {str(e)[:90]}")
    return out
