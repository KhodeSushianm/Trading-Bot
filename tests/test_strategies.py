# -*- coding: utf-8 -*-
"""میخ‌های استراتژی‌های ورود — S1 (v0.26: سه استراتژیِ صاحب‌تصویب).

اجرا:  python tests/test_strategies.py     (از ریشهٔ ریپو — آفلاین، بدون شبکه)

انضباط «اول میخ، بعد چکش»: این تست‌ها رفتار ماژول‌های src/strategies/* و
adapterهای registry را *قبل از سوییچ S3* پین می‌کنند. در S3 (وصل‌شدن داور
به استراتژی‌ها) **همین فایل بدون تغییر** باید سبز بماند؛ میخ‌های متأثرِ
داور/چرخه جداگانه و با دلیلِ مستند بازضبط می‌شوند.

پوشش:
  A) trend_pullback — هر شاخهٔ رد (روند/هم‌جهتی/ADX/منطقهٔ RSI/برگشت RSI/
     کندل تأیید/نبودِ داده) + BUY و SELL طلایی + config + قطعیت
  B) london_breakout — پنجرهٔ زمان (بیرون/آخر هفته) + Range (نبود/تنگ/پهن/
     روزِ قبل) + شکست (معتبرِ بالا/پایین/لبه‌ای/داخل) + ATR نبود + config
  C) carry — اختلاف نرخ (BUY/SELL/ناچیز/نبودِ نرخ/طلا/ارزِ ناشناخته) +
     فیلترهای هم‌جهتی (رتبه‌بندی/اخبار/برچسب سیاست) + config + proposes=False
  D) registry — قرارداد odin.strategy@1 · ثبت سه پلاگین · ترتیب priority ·
     برابری adapter==ماژول · enable/disable (کلید فیچری + plugins override) ·
     پیش‌فرض‌های load_config
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.technical import SymbolAnalysis            # noqa: E402
from src.config import load_config                           # noqa: E402
from src.core.contracts import is_valid_contract_id          # noqa: E402
from src.core.config_bridge import plugin_enabled            # noqa: E402
from src.data.base import MarketData                         # noqa: E402
from src.fundamental.news import NewsItem, NewsSnapshot      # noqa: E402
from src.judge.scoring import JudgeContext                   # noqa: E402
from src.plugins import build_default_registry               # noqa: E402
from src.strategies import carry, london_breakout, trend_pullback  # noqa: E402

COUNT = 0


def A(cond: bool, msg: str) -> None:
    global COUNT
    assert cond, msg
    COUNT += 1


# ══════════════════════════════════════════════════════════════
#  سازنده‌های دادهٔ ساختگیِ قطعی
# ══════════════════════════════════════════════════════════════
def mk_a(**over) -> SymbolAnalysis:
    base = dict(symbol="EURUSD", fa_name="یورو به دلار آمریکا",
                base="EUR", quote="USD", price=1.1020, pip=0.0001,
                trend="bullish", h1_agrees=True, adx=32.0, rsi=38.0,
                rsi_rising=True, atr=0.0020, support=1.0980,
                resistance=1.1080, last_candle=None, verdict="BUY_SETUP")
    base.update(over)
    return SymbolAnalysis(**base)


def mk_h1(rows) -> pd.DataFrame:
    """rows: [(ts, open, high, low, close)] — ایندکس naive-UTC (قرارداد داده)."""
    idx = pd.DatetimeIndex([r[0] for r in rows])
    return pd.DataFrame({"Open": [r[1] for r in rows],
                         "High": [r[2] for r in rows],
                         "Low": [r[3] for r in rows],
                         "Close": [r[4] for r in rows]}, index=idx)


def mk_md(h1) -> MarketData:
    return MarketData(symbol="EURUSD", m15=h1, h1=h1, h4=h1)


DAY = datetime(2026, 9, 23)          # چهارشنبه — روزِ ثابتِ سناریوها


def asia_bars(day=DAY, hi=1.1050, lo=1.1000, n=7):
    """n کندل H1 سشن آسیا (ساعت ۰۰..n-1 UTC) با سقف/کف داده‌شده."""
    rows = []
    for h in range(n):
        ts = day.replace(hour=h)
        rows.append((ts, lo + 0.001, hi, lo, hi - 0.001))
    return rows


def last_bull(hi=1.1050, lo=1.1000):
    """کندل H1 آخرِ صعودی (close>open) + آسیای همان روز برای trend_pullback."""
    rows = asia_bars(hi=hi, lo=lo)
    rows.append((DAY.replace(hour=8), 1.1010, 1.1040, 1.1005, 1.1035))
    return rows


def last_bear():
    rows = asia_bars()
    rows.append((DAY.replace(hour=8), 1.1040, 1.1045, 1.1000, 1.1005))
    return rows


def mk_ctx(**over) -> JudgeContext:
    base = dict(jcfg={}, acfg={}, symbols_cfg=[],
                now=DAY.replace(hour=8, minute=30, tzinfo=timezone.utc),
                ranking=[], news_snap=None)
    base.update(over)
    return JudgeContext(**base)


SCFG_TP = {"enabled": True, "adx_min": 20, "rsi_buy": [30, 45],
           "rsi_sell": [55, 70]}
SCFG_LB = {"enabled": True, "asia_start_hour": 0, "asia_end_hour": 7,
           "london_open_hour": 7, "trade_window_hours": 4,
           "asia_min_bars": 5, "min_range_atr": 0.5, "max_range_atr": 3.0,
           "breakout_margin_atr": 0.15}
SCFG_CARRY = {"enabled": True, "min_diff": 1.5, "news_min_score": 4,
              # هم‌عدد با config.yaml (v0.29: AUD 4.60 از 2026-09-29)
              "rates": {"as_of": "2026-09-29",
                        "values": {"USD": 3.88, "EUR": 2.50, "GBP": 3.75,
                                   "JPY": 1.25, "AUD": 4.60, "CAD": 2.25,
                                   "CHF": 0.00, "XAU": None},
                        "bias": {c: "neutral" for c in
                                 ("USD", "EUR", "GBP", "JPY", "AUD", "CAD",
                                  "CHF", "XAU")}}}

print("═" * 66)
print("میخ‌های استراتژی‌های ورود — S1 (v0.26)")
print("═" * 66)

# ══════════════════════════════════════════════════════════════
#  A) trend_pullback — روند + پولبک + تأیید ادامه
# ══════════════════════════════════════════════════════════════
md_bull = mk_md(mk_h1(last_bull()))
v = trend_pullback.evaluate(mk_a(), md_bull, SCFG_TP, mk_ctx())
A(v.direction == "BUY", f"ستاپ کامل صعودی باید BUY دهد، {v.direction} داد")
A(v.proposes is True, "trend_pullback باید منبعِ جهت باشد (proposes=True)")
A(v.key == "trend_pullback" and v.name_fa == "روند + پولبک",
    "کلید/نام فارسی استراتژی ۱ پین است")
A(len(v.reasons_fa) == 3, "سه دلیلِ عددی برای ستاپِ کامل")
A(v.strength > 0.6 and v.strength <= 1.0,
    f"قدرت باید در (0.6, 1.0] باشد، {v.strength} است")
A("BUY" in v.detail_fa, "detail_fa باید جهت را بگوید")

# شاخه‌های رد — هر شرط به‌تنهایی
v = trend_pullback.evaluate(mk_a(rsi_rising=False), md_bull, SCFG_TP, mk_ctx())
A(v.direction == "NONE" and "RSI" in v.reasons_fa[0],
    "بدونِ برگشت RSI، تأیید ادامه نیست → NONE")
v = trend_pullback.evaluate(mk_a(), mk_md(mk_h1(last_bear())), SCFG_TP, mk_ctx())
A(v.direction == "NONE" and "کندل آخر ۱ ساعته" in v.reasons_fa[0],
    "کندل خلاف جهت → تأیید ادامه نیست → NONE")
v = trend_pullback.evaluate(mk_a(rsi=50.0), md_bull, SCFG_TP, mk_ctx())
A(v.direction == "NONE" and "پولبک معتبر نیست" in v.reasons_fa[0],
    "RSI بیرون منطقه → پولبک معتبر نیست")
v = trend_pullback.evaluate(mk_a(rsi=25.0), md_bull, SCFG_TP, mk_ctx())
A(v.direction == "NONE" and "پولبک معتبر نیست" in v.reasons_fa[0],
    "RSI زیر کفِ منطقه (۲۵<۳۰) هم رد است — ورود در سقوطِ آزاد نه")
v = trend_pullback.evaluate(mk_a(trend="bearish", h1_agrees=True, adx=28.0,
                                 rsi=62.0, rsi_rising=False),
                            mk_md(mk_h1(last_bear())), SCFG_TP, mk_ctx())
A(v.direction == "SELL", f"آینهٔ نزولی کامل باید SELL دهد، {v.direction} داد")
v = trend_pullback.evaluate(mk_a(trend="bearish", h1_agrees=True, adx=28.0,
                                 rsi=62.0, rsi_rising=True),
                            mk_md(mk_h1(last_bear())), SCFG_TP, mk_ctx())
A(v.direction == "NONE", "در روند نزولی، RSIِ بالارونده = تأیید ادامه نیست")
v = trend_pullback.evaluate(mk_a(adx=15.0), md_bull, SCFG_TP, mk_ctx())
A(v.direction == "NONE" and "روند معتبر نیست" in v.reasons_fa[0],
    "ADX زیر آستانه → روند معتبر نیست")
v = trend_pullback.evaluate(mk_a(h1_agrees=False), md_bull, SCFG_TP, mk_ctx())
A(v.direction == "NONE" and "جهت غالب تأیید نشده" in v.reasons_fa[0],
    "بدون هم‌جهتی H1 → جهت غالب تأیید نشده")
v = trend_pullback.evaluate(mk_a(trend="none"), md_bull, SCFG_TP, mk_ctx())
A(v.direction == "NONE" and "نامشخص" in v.reasons_fa[0],
    "روند نامشخص → NONE")
v = trend_pullback.evaluate(mk_a(), None, SCFG_TP, mk_ctx())
A(v.direction == "NONE" and "در دسترس نیست" in v.reasons_fa[0],
    "نبودِ کندل → ردِ صادقانه، نه حدس")

# config محترم است + قطعیت + یکنواختی قدرت
cfg40 = dict(SCFG_TP, adx_min=40)
v = trend_pullback.evaluate(mk_a(adx=32.0), md_bull, cfg40, mk_ctx())
A(v.direction == "NONE", "adx_min=40 باید ستاپ ADX=32 را رد کند (config محترم است)")
d1 = trend_pullback.evaluate(mk_a(), md_bull, SCFG_TP, mk_ctx()).to_dict()
d2 = trend_pullback.evaluate(mk_a(), md_bull, SCFG_TP, mk_ctx()).to_dict()
A(d1 == d2, "استراتژی ۱ باید قطعی باشد (دو فراخوانی = یک dict)")
s_low = trend_pullback.evaluate(mk_a(adx=25.0), md_bull, SCFG_TP, mk_ctx()).strength
s_high = trend_pullback.evaluate(mk_a(adx=45.0), md_bull, SCFG_TP, mk_ctx()).strength
A(s_high > s_low and s_high <= 1.0, "ADX قوی‌تر = ستاپ قوی‌تر (یکنوا و کران‌دار)")
print(f"✅ A) trend_pullback — {COUNT} میخ سبز")
COUNT_A = COUNT

# ══════════════════════════════════════════════════════════════
#  B) london_breakout — شکست محدودهٔ آسیا در پنجرهٔ لندن
# ══════════════════════════════════════════════════════════════
md_lb = mk_md(mk_h1(asia_bars()))
NOW = DAY.replace(hour=8, minute=30, tzinfo=timezone.utc)

v = london_breakout.evaluate(mk_a(price=1.1060), md_lb, SCFG_LB, mk_ctx(now=NOW))
A(v.direction == "BUY", f"بستهٔ بالای سقف+حاشیه باید BUY دهد، {v.direction} داد")
A(v.proposes is True and v.key == "london_breakout",
    "شکست لندن منبعِ جهت است (proposes=True)")
A(len(v.reasons_fa) == 3 and "محدودهٔ آسیا" in v.reasons_fa[0],
    "دلیل‌ها باید عددِ محدوده/شکست/پنجره را بگویند")
v = london_breakout.evaluate(mk_a(price=1.0990), md_lb, SCFG_LB, mk_ctx(now=NOW))
A(v.direction == "SELL", "بستهٔ زیر کف−حاشیه باید SELL دهد")
v = london_breakout.evaluate(mk_a(price=1.1052), md_lb, SCFG_LB, mk_ctx(now=NOW))
A(v.direction == "NONE" and "شکست معتبری رخ نداده" in v.reasons_fa[0],
    "عبور از سقف بدون ردِ حاشیهٔ نفوذ (0.15×ATR) → شکست لبه‌ای رد است")
v = london_breakout.evaluate(mk_a(price=1.1020), md_lb, SCFG_LB, mk_ctx(now=NOW))
A(v.direction == "NONE" and "شکست معتبری رخ نداده" in v.reasons_fa[0],
    "قیمت داخل محدوده → NONE")

# پنجرهٔ زمان
for hh, mm in ((12, 0), (6, 59), (11, 0)):
    now_x = DAY.replace(hour=hh, minute=mm, tzinfo=timezone.utc)
    v = london_breakout.evaluate(mk_a(price=1.1060), md_lb, SCFG_LB, mk_ctx(now=now_x))
    A(v.direction == "NONE" and "بیرونِ پنجرهٔ شکستِ لندن" in v.reasons_fa[0],
        f"ساعت {hh:02d}:{mm:02d} بیرون پنجرهٔ ۰۷–۱۱ UTC است → NONE")
now_sat = (DAY + timedelta(days=3)).replace(hour=8, minute=30, tzinfo=timezone.utc)
v = london_breakout.evaluate(mk_a(price=1.1060), md_lb, SCFG_LB, mk_ctx(now=now_sat))
A(v.direction == "NONE" and "پایانی هفته" in v.reasons_fa[0],
    "شنبه — سشن لندن بسته است → NONE")

# Range
narrow = mk_md(mk_h1(asia_bars(hi=1.1005, lo=1.1000)))
v = london_breakout.evaluate(mk_a(price=1.1060), narrow, SCFG_LB, mk_ctx(now=NOW))
A(v.direction == "NONE" and "خیلی تنگ" in v.reasons_fa[0],
    "عرض 0.0005 < 0.5×ATR → محدودهٔ نویزی رد است")
wide = mk_md(mk_h1(asia_bars(hi=1.1080, lo=1.1000)))
v = london_breakout.evaluate(mk_a(price=1.1200), wide, SCFG_LB, mk_ctx(now=NOW))
A(v.direction == "NONE" and "خیلی پهن" in v.reasons_fa[0],
    "عرض 0.008 > 3×ATR → حرکتِ روزِ قبل، رد است")
short = mk_md(mk_h1(asia_bars(n=3)))
v = london_breakout.evaluate(mk_a(price=1.1060), short, SCFG_LB, mk_ctx(now=NOW))
A(v.direction == "NONE" and "کامل تشکیل نشده" in v.reasons_fa[0],
    "۳ کندل آسیا < asia_min_bars=5 → Range معتبر نیست")
yday = mk_md(mk_h1(asia_bars(day=DAY - timedelta(days=1))))
v = london_breakout.evaluate(mk_a(price=1.1060), yday, SCFG_LB, mk_ctx(now=NOW))
A(v.direction == "NONE" and "کامل تشکیل نشده" in v.reasons_fa[0],
    "کندل‌های آسیایِ *دیروز* شمرده نمی‌شوند — مرزِ روزِ UTC پین است")
v = london_breakout.evaluate(mk_a(price=1.1060, atr=0.0), md_lb, SCFG_LB, mk_ctx(now=NOW))
A(v.direction == "NONE" and "ATR در دسترس نیست" in v.reasons_fa[0],
    "ATR=0 → بدون سنجشِ اعتبار، NONE صادقانه")
v = london_breakout.evaluate(mk_a(price=1.1060), None, SCFG_LB, mk_ctx(now=NOW))
A(v.direction == "NONE" and "در دسترس نیست" in v.reasons_fa[0],
    "نبودِ کندل → NONE صادقانه")

# config + قطعیت + nowِ naive/aware یکسان
cfg_w8 = dict(SCFG_LB, trade_window_hours=8)
v = london_breakout.evaluate(mk_a(price=1.1060), md_lb, cfg_w8,
                             mk_ctx(now=DAY.replace(hour=12, tzinfo=timezone.utc)))
A(v.direction == "BUY", "trade_window_hours=8 باید ساعت ۱۲ را داخل پنجره بیاورد")
now_naive = DAY.replace(hour=8, minute=30)     # naive = UTC (قرارداد داده)
v1 = london_breakout.evaluate(mk_a(price=1.1060), md_lb, SCFG_LB, mk_ctx(now=now_naive))
v2 = london_breakout.evaluate(mk_a(price=1.1060), md_lb, SCFG_LB, mk_ctx(now=NOW))
A(v1.to_dict() == v2.to_dict(), "nowِ naive-UTC و aware-UTC باید یک نتیجه دهند")
d1 = london_breakout.evaluate(mk_a(price=1.1060), md_lb, SCFG_LB, mk_ctx(now=NOW)).to_dict()
d2 = london_breakout.evaluate(mk_a(price=1.1060), md_lb, SCFG_LB, mk_ctx(now=NOW)).to_dict()
A(d1 == d2, "استراتژی ۲ باید قطعی باشد")
s_edge = london_breakout.evaluate(mk_a(price=1.1055), md_lb, SCFG_LB, mk_ctx(now=NOW)).strength
s_far = london_breakout.evaluate(mk_a(price=1.1090), md_lb, SCFG_LB, mk_ctx(now=NOW)).strength
A(s_far > s_edge and s_far <= 1.0, "نفوذِ بیشتر = شکستِ قوی‌تر (یکنوا و کران‌دار)")
print(f"✅ B) london_breakout — {COUNT - COUNT_A} میخ سبز")
COUNT_B = COUNT

# ══════════════════════════════════════════════════════════════
#  C) carry — صرفِ نرخ بهره + هم‌جهتی فاندامنتال
# ══════════════════════════════════════════════════════════════
def mk_pair(symbol, base, quote):
    return mk_a(symbol=symbol, base=base, quote=quote)

v = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY, mk_ctx())
A(v.direction == "BUY", f"AUD(4.60)−JPY(1.25)=+3.35 باید BUY دهد، {v.direction} داد")
A(v.proposes is False, "carry فقط «توافق» است — proposes=False پین است")
A(abs(v.strength - 1.0) < 1e-9, "اختلاف ۳٫۱ ≥ ۲×min_diff → strength=1.0")
A("2026-09" in v.reasons_fa[-1], "منبع/تاریخِ جدول باید در دلیل‌ها صادقانه بیاید")
v = carry.evaluate(mk_pair("USDJPY", "USD", "JPY"), None, SCFG_CARRY, mk_ctx())
A(v.direction == "BUY", "USD−JPY=+2.63 → BUY")
v = carry.evaluate(mk_pair("EURCHF", "EUR", "CHF"), None, SCFG_CARRY, mk_ctx())
A(v.direction == "BUY", "EUR−CHF=+2.50 → BUY")
v = carry.evaluate(mk_pair("JPYUSD", "JPY", "USD"), None, SCFG_CARRY, mk_ctx())
A(v.direction == "SELL", "JPY−USD=−2.63 → SELL (آینه)")
v = carry.evaluate(mk_pair("EURUSD", "EUR", "USD"), None, SCFG_CARRY, mk_ctx())
A(v.direction == "NONE" and "زیر آستانهٔ" in v.reasons_fa[0],
    "EUR−USD=−1.38 و |1.38|<1.5 → صرفِ ناچیز، NONE")
v = carry.evaluate(mk_pair("XAUUSD", "XAU", "USD"), None, SCFG_CARRY, mk_ctx())
A(v.direction == "NONE" and "در جدول نیست" in v.reasons_fa[0],
    "طلا نرخ بهره ندارد (XAU=null) → NONE صادقانه")
v = carry.evaluate(mk_pair("BTCUSD", "BTC", "USD"), None, SCFG_CARRY, mk_ctx())
A(v.direction == "NONE" and "در جدول نیست" in v.reasons_fa[0],
    "ارزِ بدون نرخ در جدول → NONE (هرگز حدس نه)")

# فیلتر ۳) جهت Macro — رتبه‌بندی قدرت
rk_bad = [("JPY", 9.0), ("AUD", 5.0)]
v = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
                   mk_ctx(ranking=rk_bad))
A(v.direction == "NONE" and "جریانِ قدرت خلاف" in v.reasons_fa[0],
    "برای BUY، ضعفِ پایه در رتبه‌بندی → رد")
rk_ok = [("AUD", 9.0), ("JPY", 5.0)]
v = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
                   mk_ctx(ranking=rk_ok))
A(v.direction == "BUY", "رتبه‌بندی هم‌جهت → BUY برقرار")
v = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
                   mk_ctx(ranking=[]))
A(v.direction == "BUY", "نبودِ رتبه‌بندی → فیلتر صادقانه رد نمی‌کند")

# فیلتر ۴) هم‌جهتی اخبار
snap_against = NewsSnapshot(items=[NewsItem(title="RBA dovish surprise",
                                            score=5, direction={"AUD": -1})])
v = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
                   mk_ctx(news_snap=snap_against))
A(v.direction == "NONE" and "پشتیبانی نمی‌کنند" in v.reasons_fa[0],
    "رأی اخبار خلاف جهت carry → NONE")
snap_for = NewsSnapshot(items=[NewsItem(title="RBA hawkish hold",
                                        score=5, direction={"AUD": 1, "JPY": -1})])
v = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY,
                   mk_ctx(news_snap=snap_for))
A(v.direction == "BUY", "اخبار هم‌جهت → BUY برقرار")

# فیلتر ۲) برچسب سیاست پولی
sc_hawk = {"enabled": True, "min_diff": 1.5, "news_min_score": 4,
           "rates": dict(SCFG_CARRY["rates"],
                         bias=dict(SCFG_CARRY["rates"]["bias"], JPY="hawkish"))}
v = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None, sc_hawk, mk_ctx())
A(v.direction == "NONE" and "سیاست پولی خلاف" in v.reasons_fa[0],
    "quote=JPY hawkish خلاف جهت BUY → رد")
sc_dov = {"enabled": True, "min_diff": 1.5, "news_min_score": 4,
          "rates": dict(SCFG_CARRY["rates"],
                        bias=dict(SCFG_CARRY["rates"]["bias"], AUD="dovish"))}
v = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None, sc_dov, mk_ctx())
A(v.direction == "NONE" and "سیاست پولی خلاف" in v.reasons_fa[0],
    "base=AUD dovish خلاف جهت BUY → رد")

# config + قطعیت
v = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None,
                   dict(SCFG_CARRY, min_diff=3.5), mk_ctx())
A(v.direction == "NONE", "min_diff=3.5 باید +3.10 را رد کند (config محترم است)")
d1 = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY, mk_ctx()).to_dict()
d2 = carry.evaluate(mk_pair("AUDJPY", "AUD", "JPY"), None, SCFG_CARRY, mk_ctx()).to_dict()
A(d1 == d2, "استراتژی ۳ باید قطعی باشد")
print(f"✅ C) carry — {COUNT - COUNT_B} میخ سبز")
COUNT_C = COUNT

# ══════════════════════════════════════════════════════════════
#  D) registry / config — قرارداد و adapterها
# ══════════════════════════════════════════════════════════════
A(is_valid_contract_id("odin.strategy@1"),
    "odin.strategy@1 باید قراردادِ ثبت‌شدهٔ هسته باشد")
cfg = load_config(str(ROOT / "config.yaml"))
A(cfg["strategies"]["min_agree"] == 1, "min_agree پیش‌فرض = ۱")
A(cfg["strategies"]["carry"]["rates"]["values"]["USD"] == 3.88,
    "جدول نرخ‌ها باید از config.yaml خوانده شود (USD=3.88)")
# v0.29: as_of و AUD هم صریحاً پین شدند — این جدول دستی است و کهنه‌شدنش
# یک باگِ بی‌صداست (کاری که پیش از این نسخه اتفاق افتاده بود).
A(cfg["strategies"]["carry"]["rates"]["as_of"] == "2026-09-29",
    f"as_of باید تاریخِ آخرین تصمیمِ بانک مرکزی باشد "
    f"({cfg['strategies']['carry']['rates']['as_of']})")
A(cfg["strategies"]["carry"]["rates"]["values"]["AUD"] == 4.60,
    f"AUD=4.60 (RBA در 2026-09-29) — "
    f"{cfg['strategies']['carry']['rates']['values']['AUD']}")
A(cfg["strategies"]["carry"]["rates"]["values"]["XAU"] is None,
    "XAU=null — طلای بی‌نرخ")

reg, info = build_default_registry(cfg)
ids = [r.id for r in reg.all()]
for pid in ("strategy-trend-pullback", "strategy-london-breakout", "strategy-carry"):
    A(pid in ids, f"پلاگین «{pid}» باید در registry ثبت شود")
A(len(reg.all()) == 33, f"registry باید ۳۳ پلاگین داشته باشد، {len(reg.all())} است")
provs = reg.providers("odin.strategy@1")
A([p.id for p in provs] == ["strategy-trend-pullback", "strategy-london-breakout",
                            "strategy-carry"],
    "ترتیب فراهم‌کنندگان = priority اعلامی (۱۰/۲۰/۳۰)")

# adapter == فراخوانی مستقیم (delegation خالص — بایت‌به‌بایت)
ctx = mk_ctx()
cases = [("trend_pullback", mk_a(), md_bull),
         ("london_breakout", mk_a(price=1.1060), md_lb),
         ("carry", mk_pair("AUDJPY", "AUD", "JPY"), None)]
mods = {"trend_pullback": trend_pullback, "london_breakout": london_breakout,
        "carry": carry}
scfgs = {"trend_pullback": SCFG_TP, "london_breakout": SCFG_LB, "carry": SCFG_CARRY}
for rec, (key, a, md) in zip(provs, cases):
    inst = rec.instance if rec.instance is not None else rec.factory(info["context"])
    got = inst.evaluate(a, md, ctx).to_dict()
    want = mods[key].evaluate(a, md, cfg["strategies"][key], ctx).to_dict()
    A(got == want, f"adapter «{rec.id}» باید بایت‌به‌بایت == ماژول باشد")
    A(got["direction"] in ("BUY", "SELL", "NONE"), "direction معتبر")

# enable/disable — کلید فیچری و plugins override
cfg_off = load_config(str(ROOT / "config.yaml"))
cfg_off["strategies"]["carry"]["enabled"] = False
reg2, _ = build_default_registry(cfg_off)
A(plugin_enabled(cfg_off, [r.manifest for r in reg2.all()
                           if r.id == "strategy-carry"][0]) is False,
    "strategies.carry.enabled=false باید پلاگین را خاموش کند")
A([p.id for p in reg2.providers("odin.strategy@1")]
  == ["strategy-trend-pullback", "strategy-london-breakout"],
    "استراتژی خاموش باید از فهرست فراهم‌کنندگان حذف شود")
cfg_ov = load_config(str(ROOT / "config.yaml"))
cfg_ov["plugins"] = {"strategy-london-breakout": {"enabled": False}}
reg3, _ = build_default_registry(cfg_ov)
A([p.id for p in reg3.providers("odin.strategy@1")]
  == ["strategy-trend-pullback", "strategy-carry"],
    "plugins override صریح باید برنده شود (فاز ۷)")
A(any("strategy" in line for line in info["log"]),
    "لاگ ثبت پلاگین‌ها باید استراتژی‌ها را نشان دهد")
print(f"✅ D) registry/config — {COUNT - COUNT_C} میخ سبز")

print("═" * 66)
print(f"🎯 همهٔ {COUNT} میخِ استراتژی‌ها سبز است "
      f"(A={COUNT_A}، B={COUNT_B - COUNT_A}، C={COUNT_C - COUNT_B}، "
      f"D={COUNT - COUNT_C})")
print("═" * 66)
