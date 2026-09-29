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

# ── v0.29: دو قیمت، دو نقش (پیش‌تر یکی بودند و همین ریشهٔ باگ بود) ──
#   `price`      = بستهٔ H1 — لنگرِ *تحلیل*: انتخابِ نزدیک‌ترین حمایت/مقاومت
#                  و سنجشِ فاصله تا سطح کلیدی (ev_level). دست‌نخورده ماند تا
#                  امتیازدهی و وتوها بایت‌به‌بایت همان قبلی باشند.
#   `exec_price` = بستهٔ M15 — قیمتِ *اجرا*: آنچه کاربر در عمل می‌تواند با
#                  آن وارد شود. مبنای entry/sl/tp/sid/ژورنال.
# کهنگیِ exec_price با drop_forming_candle حداکثر ۱۵ دقیقه است (پیش‌تر تا
# ~۷۵ دقیقه). EXEC_TF_MIN/H1_TF_MIN طولِ بازه‌اند، برای محاسبهٔ زمانِ بسته‌شدن.
EXEC_TF_MIN = 15
H1_TF_MIN = 60


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
    # ── v0.29: قیمت و زمانِ *اجرا* ────────────────────────────────
    # None یعنی «این تحلیل قیمتِ اجرا ندارد» (مثلاً SymbolAnalysisِ دستیِ
    # تست‌ها) → مصرف‌کننده صادقانه به `price` برمی‌گردد، نه به صفر.
    # exec_ts زمانِ بسته‌شدنِ همان کندلی است که exec_price از آن آمده؛
    # ژورنال آن را entry_ts می‌نویسد و tracker اسکن را از آنجا شروع می‌کند.
    exec_price: Optional[float] = None
    exec_ts: Optional[datetime] = None


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
            exec_price=_exec_price(m15, h1),
            exec_ts=_exec_ts(m15, h1),
        )

    price = float(h1["Close"].iloc[-1])

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
        exec_price=_exec_price(m15, h1), exec_ts=_exec_ts(m15, h1),
    )


def _last_ts(df) -> Optional[datetime]:
    try:
        ts = df.index[-1]
        return ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.fromisoformat(str(ts))
    except Exception:
        return None


def _exec_price(m15, h1) -> Optional[float]:
    """قیمتِ اجرا = بستهٔ تازه‌ترین کندلِ M15.

    اگر M15 خالی/خراب بود، صادقانه ``None`` برمی‌گرداند تا مصرف‌کننده به
    ``price`` (بستهٔ H1) برگردد — یعنی رفتارِ پیش از v0.29، نه عددِ ساختگی.
    """
    try:
        if m15 is not None and len(m15):
            return float(m15["Close"].iloc[-1])
    except Exception:
        pass
    return None


def _exec_ts(m15, h1) -> Optional[datetime]:
    """زمانِ بسته‌شدنِ کندلی که ``_exec_price`` از آن آمده.

    باید با ``_exec_price`` هم‌منبع باشد، وگرنه همان باگِ «قیمت از یک لحظه،
    اسکن از لحظهٔ دیگر» برمی‌گردد. M15 خالی → زمانِ بستهٔ H1 (هم‌راستا با
    بازگشتِ قیمت به ``price``).
    """
    if m15 is not None and len(m15):
        return _close_ts(m15, EXEC_TF_MIN)
    return _close_ts(h1, H1_TF_MIN)


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
