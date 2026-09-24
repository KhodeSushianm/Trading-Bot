# -*- coding: utf-8 -*-
"""تولیدکنندهٔ طلاییِ پاریتیِ استراتژی‌ها — S2 (اوراکل پایتون → JS).

ایده (انضباط «اول میخ، بعد چکش» — همان الگوی gen_judge_golden.py):
  ۱) این اسکریپت باتری سناریوهای سه استراتژی را با دادهٔ **ساختگیِ قطعی**
     و **بدون شبکه** روی ماژول‌های *پایتون* (src/strategies/* — اوراکل)
     اجرا می‌کند و ورودی‌ها + verdictها را در
     tests/js/golden/strategies_golden.json ضبط می‌کند.
  ۲) tests/js/test_strategies_switch.js همان ورودی‌ها را در JS بازسازی و
     آینهٔ ES5 (js/strategies.js) را صدا می‌کند؛ خروجی باید **بایت‌به‌بایت**
     با طلایی یکی باشد (متن‌های فارسی/ZWNJ/قالب اعداد/floatها).

پوشش (آینهٔ باتری tests/test_strategies.py + لبه‌های دو-زبانه):
  A) trend_pullback — شاخه‌های رد، BUY/SELL طلایی، لبهٔ منطقهٔ RSI،
     گردِ نصف-به-زوج (ADX=20.5 → «۲۰»)، NaN (رد نشدنِ ADX=nan + متنِ
     «nan»)، نبود/خالی بودن کندل‌ها
  B) london_breakout — پنجره (لبه‌های ۰۷/۱۱ و آخر هفته)، Range (تنگ/پهن/
     کوتاه/دیروز/مهرِ زمانیِ خراب)، شکست (معتبر/لبه‌ای/داخل/NaN/دقیقاً روی
     حاشیه)، ATR صفر/NaN، config
  C) carry — اختلاف نرخ (امضا +۰٫۰۰ و −۱٫۳۸)، نرخِ گم‌شده (XAU/BTC/پایهٔ
     خالی)، برچسب سیاست (چهار ترکیب BUY/SELL + برچسب نامعتبر)، رتبه‌بندی
     (خلاف/هم‌جهت/خالی/ارزِ غایب)، اخبار (خلاف/هم‌جهت/زیر آستانه/خالی)،
     نبودِ ctx، strength میانی، min_diff=NaN (پینِ pyMin مقایسه‌محور)
  D) قطعیت — دو فراخوانی از یک ورودی = یک خروجی

سریال‌سازی: NaN با نشانگر "__NaN__" (JSON استاندارد NaN ندارد) — سمت JS
بازسازی می‌شود. time = epoch-ms (UTC). h1 = [[ts, Open, High, Low, Close]].

اجرا (برای ضبط/بازتولید عمدیِ طلایی — فقط با دلیل موجه):
    python tests/js/gen_strategies_golden.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.technical import SymbolAnalysis                # noqa: E402
from src.data.base import MarketData                             # noqa: E402
from src.fundamental.news import NewsItem, NewsSnapshot          # noqa: E402
from src.judge.scoring import JudgeContext                       # noqa: E402
from src.strategies import carry, london_breakout, trend_pullback  # noqa: E402

GOLDEN_PATH = HERE / "golden" / "strategies_golden.json"
NAN = float("nan")
NAN_TOKEN = "__NaN__"

MODS = {"trend_pullback": trend_pullback, "london_breakout": london_breakout,
        "carry": carry}


# ══════════════════════════════════════════════════════════════
#  سازنده‌های دادهٔ ساختگیِ قطعی (هم‌مقدار با tests/test_strategies.py)
# ══════════════════════════════════════════════════════════════
def mk_a(**over) -> SymbolAnalysis:
    base = dict(symbol="EURUSD", fa_name="یورو به دلار آمریکا",
                base="EUR", quote="USD", price=1.1020, pip=0.0001,
                trend="bullish", h1_agrees=True, adx=32.0, rsi=38.0,
                rsi_rising=True, atr=0.0020, support=1.0980,
                resistance=1.1080, last_candle=None, verdict="BUY_SETUP")
    base.update(over)
    return SymbolAnalysis(**base)


DAY = datetime(2026, 9, 23, tzinfo=timezone.utc)     # چهارشنبه — روزِ ثابت
NOW = DAY.replace(hour=8, minute=30)                # داخل پنجرهٔ لندن


def ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def asia_bars(day=DAY, hi=1.1050, lo=1.1000, n=7):
    rows = []
    for h in range(n):
        rows.append((day.replace(hour=h), lo + 0.001, hi, lo, hi - 0.001))
    return rows


def last_bull(hi=1.1050, lo=1.1000):
    rows = asia_bars(hi=hi, lo=lo)
    rows.append((DAY.replace(hour=8), 1.1010, 1.1040, 1.1005, 1.1035))
    return rows


def last_bear():
    rows = asia_bars()
    rows.append((DAY.replace(hour=8), 1.1040, 1.1045, 1.1000, 1.1005))
    return rows


def mk_h1(rows) -> pd.DataFrame:
    idx = pd.DatetimeIndex([r[0] for r in rows])
    return pd.DataFrame({"Open": [r[1] for r in rows],
                         "High": [r[2] for r in rows],
                         "Low": [r[3] for r in rows],
                         "Close": [r[4] for r in rows]}, index=idx)


def mk_md(rows):
    if rows is None:
        return None
    df = mk_h1(rows)
    return MarketData(symbol="EURUSD", m15=df, h1=df, h4=df)


def mk_ctx(now=NOW, ranking=None, news=None) -> JudgeContext:
    return JudgeContext(jcfg={}, acfg={}, symbols_cfg=[], now=now,
                        ranking=ranking or [], news_snap=news)


def news_snap(items) -> NewsSnapshot:
    return NewsSnapshot(items=[NewsItem(**it) for it in items])


SCFG_TP = {"enabled": True, "adx_min": 20, "rsi_buy": [30, 45],
           "rsi_sell": [55, 70]}
SCFG_LB = {"enabled": True, "asia_start_hour": 0, "asia_end_hour": 7,
           "london_open_hour": 7, "trade_window_hours": 4,
           "asia_min_bars": 5, "min_range_atr": 0.5, "max_range_atr": 3.0,
           "breakout_margin_atr": 0.15}
RATES = {"as_of": "2026-09",
         "values": {"USD": 3.88, "EUR": 2.50, "GBP": 3.75, "JPY": 1.25,
                    "AUD": 4.35, "CAD": 2.25, "CHF": 0.00, "XAU": None},
         "bias": {c: "neutral" for c in ("USD", "EUR", "GBP", "JPY",
                                         "AUD", "CAD", "CHF", "XAU")}}
SCFG_CARRY = {"enabled": True, "min_diff": 1.5, "news_min_score": 4,
              "rates": RATES}


# ══════════════════════════════════════════════════════════════
#  ثبت سناریوها
# ══════════════════════════════════════════════════════════════
SCENARIOS = []


def sc(name, strategy, a, rows, scfg, ctx, a_over_json=None):
    """یک سناریو: ورودی‌ها + verdict اوراکل. rows=None → md=None.

    a_over_json: جایگزینِ serialized برای فیلدهای a (مثل حذف کلید یا NaN) —
    خودِ ارزیابی با `a` پایتون انجام می‌شود.
    """
    v = MODS[strategy].evaluate(a, mk_md(rows), scfg, ctx)
    a_json = a_over_json if a_over_json is not None else dump_a(a)
    SCENARIOS.append({
        "name": name,
        "strategy": strategy,
        "input": {
            "a": a_json,
            "h1": None if rows is None else enc(
                [[ms(r[0]) if r[0] is not None else None,
                  r[1], r[2], r[3], r[4]] for r in rows]),
            "scfg": enc(scfg),
            "ctx": dump_ctx(ctx),
        },
        "expected": enc(v.to_dict()),
    })
    return v


A_FIELDS = ("symbol", "fa_name", "base", "quote", "price", "pip", "trend",
            "h1_agrees", "adx", "rsi", "rsi_rising", "atr", "support",
            "resistance", "verdict")


def dump_a(a) -> dict:
    out = {k: enc(getattr(a, k)) for k in A_FIELDS}
    out["last_candle"] = None
    return out


def dump_ctx(ctx) -> dict:
    out = {"now_ms": ms(ctx.now), "ranking": [[c, enc(v)] for c, v in ctx.ranking]}
    if ctx.news_snap is None:
        out["news_snap"] = None
    else:
        out["news_snap"] = {"items": [
            {"title": it.title, "score": it.score, "direction": dict(it.direction),
             "roundup": bool(it.roundup), "breaking": bool(it.breaking)}
            for it in ctx.news_snap.items]}
    return out


def enc(v):
    """JSON-safe: NaN → نشانگر؛ dict/list بازگشتی؛ بقیه همان."""
    if isinstance(v, float) and math.isnan(v):
        return NAN_TOKEN
    if isinstance(v, dict):
        return {k: enc(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [enc(x) for x in v]
    return v


md_bull = last_bull()
md_lb = asia_bars()

# ── A) trend_pullback ────────────────────────────────────────────
sc("tp_buy_golden", "trend_pullback", mk_a(), md_bull, SCFG_TP, mk_ctx())
sc("tp_sell_golden", "trend_pullback",
   mk_a(trend="bearish", h1_agrees=True, adx=28.0, rsi=62.0, rsi_rising=False,
        verdict="SELL_SETUP"),
   last_bear(), SCFG_TP, mk_ctx())
sc("tp_no_rsi_rising", "trend_pullback", mk_a(rsi_rising=False), md_bull, SCFG_TP, mk_ctx())
sc("tp_candle_against", "trend_pullback", mk_a(), last_bear(), SCFG_TP, mk_ctx())
sc("tp_rsi_out_50", "trend_pullback", mk_a(rsi=50.0), md_bull, SCFG_TP, mk_ctx())
sc("tp_rsi_out_25", "trend_pullback", mk_a(rsi=25.0), md_bull, SCFG_TP, mk_ctx())
sc("tp_sell_rsi_rising", "trend_pullback",
   mk_a(trend="bearish", adx=28.0, rsi=62.0, rsi_rising=True), last_bear(),
   SCFG_TP, mk_ctx())
sc("tp_adx_low", "trend_pullback", mk_a(adx=15.0), md_bull, SCFG_TP, mk_ctx())
sc("tp_no_h1_agree", "trend_pullback", mk_a(h1_agrees=False), md_bull, SCFG_TP, mk_ctx())
sc("tp_trend_none", "trend_pullback", mk_a(trend="none"), md_bull, SCFG_TP, mk_ctx())
sc("tp_trend_null", "trend_pullback", mk_a(trend=None), md_bull, SCFG_TP, mk_ctx())
sc("tp_no_md", "trend_pullback", mk_a(), None, SCFG_TP, mk_ctx())
sc("tp_empty_h1", "trend_pullback", mk_a(), [], SCFG_TP, mk_ctx())
sc("tp_cfg_adx40", "trend_pullback", mk_a(adx=32.0), md_bull,
   dict(SCFG_TP, adx_min=40), mk_ctx())
sc("tp_adx_edge_20", "trend_pullback", mk_a(adx=20.0), md_bull, SCFG_TP, mk_ctx())
# گردِ نصف-به-زوج: f'{20.5:.0f}' → «20» (JS toFixed می‌داد «21» — پین pyFixed)
sc("tp_adx_half_even", "trend_pullback", mk_a(adx=20.5), md_bull,
   dict(SCFG_TP, adx_min=21), mk_ctx())
sc("tp_rsi_edge_30", "trend_pullback", mk_a(rsi=30.0), md_bull, SCFG_TP, mk_ctx())
sc("tp_rsi_edge_45", "trend_pullback", mk_a(rsi=45.0), md_bull, SCFG_TP, mk_ctx())
sc("tp_sell_rsi_edge_55", "trend_pullback",
   mk_a(trend="bearish", adx=28.0, rsi=55.0, rsi_rising=False), last_bear(),
   SCFG_TP, mk_ctx())
sc("tp_sell_rsi_edge_70", "trend_pullback",
   mk_a(trend="bearish", adx=28.0, rsi=70.0, rsi_rising=False), last_bear(),
   SCFG_TP, mk_ctx())
sc("tp_strength_low", "trend_pullback", mk_a(adx=25.0), md_bull, SCFG_TP, mk_ctx())
sc("tp_strength_high", "trend_pullback", mk_a(adx=45.0), md_bull, SCFG_TP, mk_ctx())
# NaN — پایتون: nan<20 → False (gate رد نمی‌کند!) و max(0.0,nan)→0.0 (strength=0.6)
sc("tp_adx_nan", "trend_pullback", mk_a(adx=NAN), md_bull, SCFG_TP, mk_ctx())
sc("tp_rsi_nan", "trend_pullback", mk_a(rsi=NAN), md_bull, SCFG_TP, mk_ctx())
sc("tp_candle_nan_close", "trend_pullback", mk_a(),
   asia_bars() + [(DAY.replace(hour=8), 1.1010, 1.1040, 1.1005, NAN)],
   SCFG_TP, mk_ctx())

# ── B) london_breakout ───────────────────────────────────────────
sc("lb_buy_golden", "london_breakout", mk_a(price=1.1060), md_lb, SCFG_LB, mk_ctx())
sc("lb_sell_golden", "london_breakout", mk_a(price=1.0990), md_lb, SCFG_LB, mk_ctx())
sc("lb_edge_no_margin", "london_breakout", mk_a(price=1.1052), md_lb, SCFG_LB, mk_ctx())
sc("lb_inside", "london_breakout", mk_a(price=1.1020), md_lb, SCFG_LB, mk_ctx())
# قیمت دقیقاً روی hi+margin — شناوریِ IEEE754 در دو زبان قطعیِ یکسان است
sc("lb_exact_margin", "london_breakout", mk_a(price=1.1053), md_lb, SCFG_LB, mk_ctx())
sc("lb_window_1200", "london_breakout", mk_a(price=1.1060), md_lb, SCFG_LB,
   mk_ctx(now=DAY.replace(hour=12)))
sc("lb_window_0659", "london_breakout", mk_a(price=1.1060), md_lb, SCFG_LB,
   mk_ctx(now=DAY.replace(hour=6, minute=59)))
sc("lb_window_1100", "london_breakout", mk_a(price=1.1060), md_lb, SCFG_LB,
   mk_ctx(now=DAY.replace(hour=11)))
sc("lb_window_open_0700", "london_breakout", mk_a(price=1.1060), md_lb, SCFG_LB,
   mk_ctx(now=DAY.replace(hour=7)))
sc("lb_saturday", "london_breakout", mk_a(price=1.1060), md_lb, SCFG_LB,
   mk_ctx(now=(DAY + timedelta(days=3)).replace(hour=8, minute=30)))
sc("lb_sunday", "london_breakout", mk_a(price=1.1060), md_lb, SCFG_LB,
   mk_ctx(now=(DAY + timedelta(days=4)).replace(hour=8, minute=30)))
sc("lb_narrow", "london_breakout", mk_a(price=1.1060),
   asia_bars(hi=1.1005, lo=1.1000), SCFG_LB, mk_ctx())
sc("lb_wide", "london_breakout", mk_a(price=1.1200),
   asia_bars(hi=1.1080, lo=1.1000), SCFG_LB, mk_ctx())
sc("lb_short", "london_breakout", mk_a(price=1.1060), asia_bars(n=3), SCFG_LB, mk_ctx())
sc("lb_yesterday", "london_breakout", mk_a(price=1.1060),
   asia_bars(day=DAY - timedelta(days=1)), SCFG_LB, mk_ctx())
sc("lb_atr_zero", "london_breakout", mk_a(price=1.1060, atr=0.0), md_lb, SCFG_LB, mk_ctx())
sc("lb_atr_nan", "london_breakout", mk_a(price=1.1060, atr=NAN), md_lb, SCFG_LB, mk_ctx())
sc("lb_price_nan", "london_breakout", mk_a(price=NAN), md_lb, SCFG_LB, mk_ctx())
sc("lb_no_md", "london_breakout", mk_a(price=1.1060), None, SCFG_LB, mk_ctx())
sc("lb_empty_h1", "london_breakout", mk_a(price=1.1060), [], SCFG_LB, mk_ctx())
sc("lb_cfg_window8", "london_breakout", mk_a(price=1.1060), md_lb,
   dict(SCFG_LB, trade_window_hours=8), mk_ctx(now=DAY.replace(hour=12)))
sc("lb_strength_far", "london_breakout", mk_a(price=1.1090), md_lb, SCFG_LB, mk_ctx())
# کندل با مهرِ زمانیِ خراب (null) باید شمرده نشود — بقیهٔ Range سالم است
sc("lb_bad_ts_bar", "london_breakout", mk_a(price=1.1060),
   [(None, 9.9, 9.9, 0.1, 9.9)] + md_lb, SCFG_LB, mk_ctx())
sc("lb_minute_msg", "london_breakout", mk_a(price=1.1060), md_lb, SCFG_LB,
   mk_ctx(now=DAY.replace(hour=9, minute=5)))

# ── C) carry ─────────────────────────────────────────────────────
def pair(symbol, base, quote):
    return mk_a(symbol=symbol, base=base, quote=quote)


sc("carry_audjpy_buy", "carry", pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY, mk_ctx())
sc("carry_usdjpy_buy", "carry", pair("USDJPY", "USD", "JPY"), None, SCFG_CARRY, mk_ctx())
sc("carry_eurchf_buy", "carry", pair("EURCHF", "EUR", "CHF"), None, SCFG_CARRY, mk_ctx())
sc("carry_jpyusd_sell", "carry", pair("JPYUSD", "JPY", "USD"), None, SCFG_CARRY, mk_ctx())
sc("carry_eurusd_tiny", "carry", pair("EURUSD", "EUR", "USD"), None, SCFG_CARRY, mk_ctx())
sc("carry_xau_none", "carry", pair("XAUUSD", "XAU", "USD"), None, SCFG_CARRY, mk_ctx())
sc("carry_btc_none", "carry", pair("BTCUSD", "BTC", "USD"), None, SCFG_CARRY, mk_ctx())
sc("carry_base_empty", "carry", pair("EURUSD", "", "USD"), None, SCFG_CARRY, mk_ctx())
sc("carry_rank_bad", "carry", pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
   mk_ctx(ranking=[("JPY", 9.0), ("AUD", 5.0)]))
sc("carry_rank_ok", "carry", pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
   mk_ctx(ranking=[("AUD", 9.0), ("JPY", 5.0)]))
sc("carry_rank_missing_cur", "carry", pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
   mk_ctx(ranking=[("EUR", 9.0), ("USD", 5.0)]))
sc("carry_rank_sell_bad", "carry", pair("JPYUSD", "JPY", "USD"), None, SCFG_CARRY,
   mk_ctx(ranking=[("JPY", 9.0), ("USD", 5.0)]))
sc("carry_news_against", "carry", pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
   mk_ctx(news=news_snap([{"title": "RBA dovish surprise", "score": 5,
                           "direction": {"AUD": -1}}])))
sc("carry_news_for", "carry", pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
   mk_ctx(news=news_snap([{"title": "RBA hawkish hold", "score": 5,
                           "direction": {"AUD": 1, "JPY": -1}}])))
sc("carry_news_low_score", "carry", pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
   mk_ctx(news=news_snap([{"title": "RBA dovish surprise", "score": 3,
                           "direction": {"AUD": -1}}])))
sc("carry_news_empty", "carry", pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
   mk_ctx(news=news_snap([])))
sc("carry_bias_quote_hawk", "carry", pair("AUDJPY", "AUD", "JPY"), None,
   {"enabled": True, "min_diff": 1.5, "news_min_score": 4,
    "rates": dict(RATES, bias=dict(RATES["bias"], JPY="hawkish"))}, mk_ctx())
sc("carry_bias_base_dov", "carry", pair("AUDJPY", "AUD", "JPY"), None,
   {"enabled": True, "min_diff": 1.5, "news_min_score": 4,
    "rates": dict(RATES, bias=dict(RATES["bias"], AUD="dovish"))}, mk_ctx())
sc("carry_bias_sell_base_hawk", "carry", pair("JPYUSD", "JPY", "USD"), None,
   {"enabled": True, "min_diff": 1.5, "news_min_score": 4,
    "rates": dict(RATES, bias=dict(RATES["bias"], JPY="hawkish"))}, mk_ctx())
sc("carry_bias_sell_quote_dov", "carry", pair("JPYUSD", "JPY", "USD"), None,
   {"enabled": True, "min_diff": 1.5, "news_min_score": 4,
    "rates": dict(RATES, bias=dict(RATES["bias"], USD="dovish"))}, mk_ctx())
sc("carry_bias_invalid_label", "carry", pair("AUDJPY", "AUD", "JPY"), None,
   {"enabled": True, "min_diff": 1.5, "news_min_score": 4,
    "rates": dict(RATES, bias=dict(RATES["bias"], AUD="HAWKISHX"))}, mk_ctx())
sc("carry_cfg_mindiff_35", "carry", pair("AUDJPY", "AUD", "JPY"), None,
   dict(SCFG_CARRY, min_diff=3.5), mk_ctx())
sc("carry_diff_zero", "carry", pair("EURUSD", "EUR", "USD"), None,
   {"enabled": True, "min_diff": 1.5, "news_min_score": 4,
    "rates": dict(RATES, values=dict(RATES["values"], EUR=2.50, USD=2.50))},
   mk_ctx())
sc("carry_strength_mid", "carry", pair("AUDJPY", "AUD", "JPY"), None,
   {"enabled": True, "min_diff": 1.0, "news_min_score": 4,
    "rates": dict(RATES, values=dict(RATES["values"], AUD=3.50, JPY=1.50))},
   mk_ctx())
# min_diff=NaN — پینِ pyMin در برابر Math.min: پایتون min(1.0, nan)=1.0
# (مقایسه‌محور) و gateٔ «abs(diff) < nan» هم False است → BUY با strength=1.0.
# JSِ Math.min-محور strength=NaN می‌داد (mutation testing این شکاف را گرفت).
sc("carry_mindiff_nan", "carry", pair("AUDJPY", "AUD", "JPY"), None,
   dict(SCFG_CARRY, min_diff=NAN), mk_ctx())
# همان min_diff=NaN ولی با اختلافِ کوچک (|−1.38| < 1.5) — پینِ عبورِ NaN از
# cfgFloat: پایتون gate را False می‌بیند → SELL؛ اگر JS نان را به پیش‌فرض
# 1.5 فروبست NONE می‌داد (mutation testing M6 این شکاف را گرفت).
sc("carry_mindiff_nan_small_diff", "carry", pair("EURUSD", "EUR", "USD"), None,
   dict(SCFG_CARRY, min_diff=NAN), mk_ctx())
# نبودِ ctx — مسیرِ ranking/news هیچ‌کدام فعال نمی‌شوند
_v = carry.evaluate(pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY, None)
SCENARIOS.append({
    "name": "carry_no_ctx", "strategy": "carry",
    "input": {"a": dump_a(pair("AUDJPY", "AUD", "JPY")), "h1": None,
              "scfg": enc(SCFG_CARRY), "ctx": None},
    "expected": enc(_v.to_dict())})

# ── D) قطعیت — دو سناریوی تکراری باید بایت‌به‌بایت یکی بمانند ─────
_d1 = len(SCENARIOS)
sc("det_tp_repeat", "trend_pullback", mk_a(), md_bull, SCFG_TP, mk_ctx())
_d2 = len(SCENARIOS)
sc("det_lb_repeat", "london_breakout", mk_a(price=1.1060), md_lb, SCFG_LB, mk_ctx())
assert SCENARIOS[_d1]["expected"] == SCENARIOS[0]["expected"], "قطعیتِ TP نقض شد"
assert SCENARIOS[_d2]["expected"] == SCENARIOS[
    [i for i, s in enumerate(SCENARIOS) if s["name"] == "lb_buy_golden"][0]
]["expected"], "قطعیتِ LB نقض شد"


def main() -> int:
    golden = {
        "meta": {
            "generator": "tests/js/gen_strategies_golden.py",
            "oracle": "src/strategies/* (پایتون — اوراکل پاریتی)",
            "consumer": "tests/js/test_strategies_switch.js (آینهٔ JS)",
            "note": "بازضبط فقط با دلیل موجه (NaN→__NaN__؛ time=epoch-ms UTC؛"
                    " h1=[[ts,Open,High,Low,Close]])",
            "count": len(SCENARIOS),
        },
        "scenarios": SCENARIOS,
    }
    GOLDEN_PATH.write_text(
        json.dumps(golden, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8")
    by = {}
    for s in SCENARIOS:
        by[s["strategy"]] = by.get(s["strategy"], 0) + 1
    dirs = {}
    for s in SCENARIOS:
        d = s["expected"]["direction"]
        dirs[d] = dirs.get(d, 0) + 1
    print(f"✅ طلاییِ پاریتیِ استراتژی‌ها ضبط شد — {GOLDEN_PATH.name}: "
          f"{len(SCENARIOS)} سناریو ({by}) — جهت‌ها: {dirs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
