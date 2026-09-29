# -*- coding: utf-8 -*-
"""موتور تحلیل تکنیکال چندتایم‌فریمی.

برای هر نماد یک SymbolAnalysis تولید می‌کند:
  - جهت روند در H4 (EMA سریع vs کند) و هم‌راستایی H1
  - قدرت روند (ADX)، مومنتوم (RSI در M15)، نوسان (ATR در H1)
  - نزدیک‌ترین حمایت/مقاومت (swing های H4)
  - verdict: کد جمع‌بندی که لایه گزارش آن را به فارسی ترجمه می‌کند
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from ..data.base import MarketData
from . import indicators as ind

# v0.29 — «قیمتِ ورود» و «زمانِ آن قیمت» باید به یک لحظه اشاره کنند.
# این ثابت می‌گوید `price` از بستهٔ کدام تایم‌فریم می‌آید (دقیقه):
#   فاز ۱ = ۶۰ (H1 — همان منبعِ فعلی؛ فقط زمانش کنارش ثبت می‌شود)
#   فاز ۲ = ۱۵ (M15 — کهنگی از ≤۷۵ دقیقه به ≤۱۵ دقیقه می‌رسد)
PRICE_TF_MIN = 60


@dataclass
class SymbolAnalysis:
    symbol: str
    fa_name: str
    base: str
    quote: str
    price: float
    pip: float
    trend: str               # bullish | bearish | none
    h1_agrees: bool
    adx: float
    rsi: float
    rsi_rising: bool
    atr: float               # واحد قیمت (H1)
    support: Optional[float]
    resistance: Optional[float]
    last_candle: Optional[datetime]
    verdict: str             # RANGE | BUY_SETUP | SELL_SETUP | WAIT | DATA
    # v0.29 (فاز ۱): زمانِ **بسته‌شدنِ** کندلی که `price` از آن آمده.
    # ژورنال این را به‌عنوان `entry_ts` ثبت می‌کند و tracker اسکنِ نتیجه را
    # از همان لحظه شروع می‌کند — نه از دیوارساعتِ لحظهٔ صدور. بدون آن،
    # قیمتِ ورود تا یک ساعت کهنه بود ولی پیگیری از «الان» شروع می‌شد و
    # کارنامه خوش‌بینانه می‌شد (باگِ v0.29؛ اندازه‌گیری‌شده در
    # tests/test_tracker.py بخش C). None = دادهٔ زمانی در دسترس نبود →
    # tracker به رفتارِ قبلی برمی‌گردد (سازگاریِ صادقانه، نه حدس).
    price_ts: Optional[datetime] = None


def analyze_symbol(sym_cfg: dict, md: MarketData, acfg: dict) -> SymbolAnalysis:
    """تحلیل کامل یک نماد بر اساس داده سه تایم‌فریم."""
    ema_fast_n = int(acfg.get("ema_fast", 50))
    ema_slow_n = int(acfg.get("ema_slow", 200))
    adx_n = int(acfg.get("adx_period", 14))
    adx_min = float(acfg.get("adx_min_trend", 20))
    rsi_n = int(acfg.get("rsi_period", 14))
    atr_n = int(acfg.get("atr_period", 14))
    swing_win = int(acfg.get("swing_window", 5))

    h4, h1, m15 = md.h4, md.h1, md.m15
    common = dict(
        symbol=sym_cfg["name"],
        fa_name=sym_cfg.get("fa", sym_cfg["name"]),
        base=sym_cfg["base"],
        quote=sym_cfg["quote"],
        pip=float(sym_cfg["pip"]),
    )

    # ── بررسی کفایت داده ──────────────────────────────────────
    if len(h4) < ema_slow_n + 10 or len(h1) < ema_slow_n + 10 or len(m15) < rsi_n + 10:
        return SymbolAnalysis(
            **common, price=float(h1["Close"].iloc[-1]) if len(h1) else 0.0,
            trend="none", h1_agrees=False, adx=0.0, rsi=50.0, rsi_rising=False,
            atr=0.0, support=None, resistance=None,
            last_candle=_last_ts(m15), verdict="DATA",
            price_ts=_close_ts(h1, PRICE_TF_MIN),
        )

    price = float(h1["Close"].iloc[-1])
    price_ts = _close_ts(h1, PRICE_TF_MIN)

    # ── روند H4 و هم‌راستایی H1 ───────────────────────────────
    e_fast_h4 = float(ind.ema(h4["Close"], ema_fast_n).iloc[-1])
    e_slow_h4 = float(ind.ema(h4["Close"], ema_slow_n).iloc[-1])
    trend = "bullish" if e_fast_h4 > e_slow_h4 else "bearish"

    e_fast_h1 = float(ind.ema(h1["Close"], ema_fast_n).iloc[-1])
    e_slow_h1 = float(ind.ema(h1["Close"], ema_slow_n).iloc[-1])
    h1_bullish = e_fast_h1 > e_slow_h1
    h1_agrees = h1_bullish if trend == "bullish" else (not h1_bullish)

    # ── سایر اندیکاتورها ──────────────────────────────────────
    adx_v = float(ind.adx(h4, adx_n).iloc[-1])
    rsi_s = ind.rsi(m15["Close"], rsi_n)
    rsi_v = float(rsi_s.iloc[-1])
    rsi_rising = bool(rsi_s.iloc[-1] > rsi_s.iloc[-2])
    atr_v = float(ind.atr(h1, atr_n).iloc[-1])
    support, resistance = ind.nearest_levels(price, h4, swing_win)

    # ── جمع‌بندی (verdict) ────────────────────────────────────
    if adx_v < adx_min:
        verdict = "RANGE"                       # وتو: بازار بی‌روند
    elif trend == "bullish" and h1_agrees and rsi_v < 45:
        verdict = "BUY_SETUP"                   # پولبک در روند صعودی
    elif trend == "bearish" and h1_agrees and rsi_v > 55:
        verdict = "SELL_SETUP"                  # اصلاح رو به بالا در روند نزولی
    else:
        verdict = "WAIT"

    return SymbolAnalysis(
        **common, price=price, trend=trend, h1_agrees=h1_agrees,
        adx=adx_v, rsi=rsi_v, rsi_rising=rsi_rising, atr=atr_v,
        support=support, resistance=resistance,
        last_candle=_last_ts(m15), verdict=verdict,
        price_ts=price_ts,
    )


def _last_ts(df) -> Optional[datetime]:
    try:
        ts = df.index[-1]
        return ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.fromisoformat(str(ts))
    except Exception:
        return None


def _close_ts(df, interval_min: int) -> Optional[datetime]:
    """زمانِ **بسته‌شدنِ** آخرین کندل = نمایهٔ آن + طولِ بازه.

    یاهو کندل‌های درون‌روزی را با نمایهٔ «زمانِ باز‌شدن» می‌دهد، پس بستهٔ
    کندلِ نمایهٔ T برابرِ قیمتِ لحظهٔ T+interval است. این همان لحظه‌ای است
    که `price` به آن تعلق دارد و tracker باید اسکن را از آنجا شروع کند.
    df خالی/خراب → None (tracker به رفتارِ قبلی برمی‌گردد؛ هرگز حدس نمی‌زنیم).
    """
    ts = _last_ts(df)
    if ts is None:
        return None
    try:
        return ts + timedelta(minutes=interval_min)
    except Exception:
        return None
