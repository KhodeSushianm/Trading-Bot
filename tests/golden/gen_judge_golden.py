# -*- coding: utf-8 -*-
"""تولیدکنندهٔ فایل طلایی داور — فاز ۴ (rule-pluginهای ۷ وتو + ۸ شاهد + risk).

ایده (انضباط «اول میخ، بعد چکش» — همان الگوی فاز ۳):
  ۱) این اسکریپت یک باتری کامل از سناریوهای داوری را با دادهٔ **ساختگیِ قطعی**
     و **بدون شبکه** روی کد *فعلی* (`src/judge/scoring`) اجرا می‌کند و نتیجهٔ
     سریال‌شده را در tests/golden/judge_rules_golden.json ضبط می‌کند
     (قبل از سوییچِ فاز ۴).
  ۲) tests/test_judge_rules.py همان باتری را تکرار و با فایل طلایی مقایسه
     می‌کند. بعد از سوییچ (استخراج ۷ تابع وتو + adapterهای پلاگین)، تست باید
     **بدون هیچ تغییری** سبز بماند — یعنی ترتیب/آستانه‌ها/متن‌های فارسی
     بایت‌به‌بایت حفظ شده‌اند.

پوشش باتری:
  • veto_single        — شلیک تکی هر ۷ وتو (کلید + عنوان + متن کامل)
  • veto_multi         — چند وتوی هم‌زمان با ترتیب دقیقِ امروز
  • veto_toggle_off    — خاموش‌کردن یک وتو با *همان کلید فعلی* config
  • veto_clean         — ستاپ سالم → بدون وتو
  • evidence_branches  — هر ۸ شاهد، همهٔ شاخه‌های امتیازی/متنی (۳۵ حالت)
  • judge_full_*       — چرخهٔ کامل BUY و SELL با سیگنال ۱۱/۱۱
  • judge_low_score    — زیر آستانه + جمع‌شدن هشدارهای ⚠️
  • judge_no_setup     — هر ۵ دلیلِ «ستاپی شکل نگرفته»
  • judge_capped       — سقف سیگنال در چرخه (max_signals_per_cycle=1)
  • judge_all_mixed    — judge_all با ۴ نماد در ۴ سرنوشت متفاوت
  • risk_math          — ریاضی SL/TP (سطح/ATR/سقف/کف/ATR صفر)

اجرا (برای ضبط/بازتولید عمدیِ طلایی — فقط با دلیل موجه):
    python tests/golden/gen_judge_golden.py

build_battery(judge_symbol_fn, judge_all_fn): پارامترهای *اختیاریِ* تزریق —
پیش‌فرض None = مسیر مستقیم scoring (همان میخ). tests/test_plugins.py با
تزریقِ مسیر rule-plugin (JudgePlugin + registry) همان باتری را اجرا می‌کند و
خروجی باید بایت‌به‌بایت با همین طلایی یکی باشد.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.technical import SymbolAnalysis                  # noqa: E402
from src.config import load_config                                 # noqa: E402
from src.data.base import MarketData                               # noqa: E402
from src.data.tradingview import TVSnapshot                        # noqa: E402
from src.fundamental.calendar import CalendarEvent, CalendarSnapshot  # noqa: E402
from src.fundamental.news import NewsItem, NewsSnapshot            # noqa: E402
from src.judge.scoring import (JudgeContext, collect_vetoes,       # noqa: E402
                               compute_levels, ev_fundamental, ev_level,
                               ev_momentum, ev_news, ev_session, ev_strength,
                               ev_tradingview, ev_trend, judge_all,
                               judge_config, judge_symbol)
from src.judge.session import market_status                        # noqa: E402

GOLDEN_PATH = HERE / "judge_rules_golden.json"

# لحظه‌های ثابت و قطعی (۲۰۲۶-۰۹-۲۳ چهارشنبه است — همان تقویمِ test_judge دستی)
WED_OVERLAP = datetime(2026, 9, 23, 14, 0, tzinfo=timezone.utc)   # هم‌پوشانی لندن/NY
WED_LONDON = datetime(2026, 9, 23, 8, 0, tzinfo=timezone.utc)     # فقط لندن (نقدشونده)
WED_THIN = datetime(2026, 9, 23, 3, 0, tzinfo=timezone.utc)       # توکیو/سیدنی (کم‌نقدینگی)
SAT = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)           # شنبه — بازار بسته

CFG = load_config()
ACFG = CFG["analysis"]
JCFG = CFG["judge"]
SYMS = CFG["symbols"]

RANK_DEFAULT = [("EUR", 0.30), ("GBP", 0.10), ("USD", -0.20), ("JPY", -0.40)]
RANK_USD_STRONG = [("USD", 0.30), ("GBP", 0.10), ("EUR", -0.20), ("JPY", -0.40)]
TV_BUY = {"EURUSD": TVSnapshot("EURUSD", 1.149, 41.0, 32.0, "BUY", 13, 4, 9)}
TV_SELL = {"EURUSD": TVSnapshot("EURUSD", 1.149, 41.0, 32.0, "SELL", 4, 13, 9)}
TV_NEUTRAL = {"EURUSD": TVSnapshot("EURUSD", 1.149, 41.0, 32.0, "NEUTRAL", 6, 6, 13)}


# ══════════════════════════════════════════════════════════════
#  سازنده‌های دادهٔ ساختگیِ قطعی (الگو از tests/manual/test_judge.py)
# ══════════════════════════════════════════════════════════════
def make_md(symbol: str = "EURUSD", n: int = 300, base: float = 1.1490,
            atr: float = 0.0010, seed: int = 7, last_spike: float = 1.0) -> MarketData:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-08-20", periods=n, freq="1h")
    close = base + np.cumsum(rng.normal(0, atr * 0.6, n))
    half = rng.uniform(0.35, 0.95, n) * atr
    high, low = close + half, close - half
    high[-1] = close[-1] + half[-1] * last_spike * 6      # کندل آخر را پرنوسان کن
    low[-1] = close[-1] - half[-1] * last_spike * 6
    open_ = close + rng.normal(0, atr * 0.2, n)
    h1 = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close}, index=idx)
    m15 = h1.iloc[-96:].copy()
    h4 = h1.iloc[-(4 * 250):].resample("4h").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    return MarketData(symbol=symbol, m15=m15, h1=h1, h4=h4)


def make_analysis(**kw) -> SymbolAnalysis:
    d = dict(symbol="EURUSD", fa_name="یورو به دلار آمریکا", base="EUR", quote="USD",
             price=1.1490, pip=0.0001, trend="bullish", h1_agrees=True, adx=32.0,
             rsi=38.0, rsi_rising=True, atr=0.0010, support=1.1486, resistance=1.1560,
             last_candle=WED_OVERLAP, verdict="BUY_SETUP")
    d.update(kw)
    return SymbolAnalysis(**d)


def make_ctx(now: datetime = WED_OVERLAP, cal=None, news=None, ranking=None,
             tv=None, **jover) -> JudgeContext:
    jcfg = dict(JCFG)
    jcfg.update(jover)
    return JudgeContext(jcfg=jcfg, acfg=ACFG, symbols_cfg=SYMS,
                        ranking=RANK_DEFAULT if ranking is None else ranking,
                        tv_map=TV_BUY if tv is None else tv,
                        cal_snap=cal, news_snap=news, now=now,
                        status=market_status(now), event_veto_minutes=30.0)


def clean_cal() -> CalendarSnapshot:
    """تقویمی با رویدادهای دور (پنجرهٔ فاندامنتال پاک است)."""
    return CalendarSnapshot(events=[CalendarEvent(
        when=WED_OVERLAP + timedelta(days=4), country="USD", title="CPI y/y",
        title_fa="تورم سالانه", impact="HIGH", forecast="2.1%", previous="2.0%",
        category="تورم", polarity=1)], fetched=True, week_range=("2026-09-20", "2026-09-26"))


def near_cal(now: datetime) -> CalendarSnapshot:
    """رویداد پراثر ۱۲ دقیقه دیگر → وتوی EVENT."""
    return CalendarSnapshot(events=[CalendarEvent(
        when=now + timedelta(minutes=12), country="USD", title="Federal Funds Rate",
        title_fa="نرخ بهره فدرال رزرو", impact="HIGH", forecast="4.00%", previous="3.75%")],
        fetched=True, week_range=("2026-09-20", "2026-09-26"))


def high_soon_cal(now: datetime) -> CalendarSnapshot:
    """رویداد پراثر ۲ ساعت دیگر — بیرون پنجرهٔ وتو، داخل پنجرهٔ فاندامنتال."""
    return CalendarSnapshot(events=[CalendarEvent(
        when=now + timedelta(hours=2), country="USD", title="CPI y/y",
        title_fa="تورم سالانه", impact="HIGH", forecast="2.1%", previous="2.0%")],
        fetched=True, week_range=("2026-09-20", "2026-09-26"))


def med_soon_cal(now: datetime) -> CalendarSnapshot:
    """فقط رویداد متوسط ۱ ساعت دیگر → فاندامنتال ۱ امتیاز."""
    return CalendarSnapshot(events=[CalendarEvent(
        when=now + timedelta(hours=1), country="USD", title="Core Retail Sales m/m",
        title_fa="خرده‌فروشی هسته", impact="MEDIUM", forecast="0.3%", previous="0.1%")],
        fetched=True, week_range=("2026-09-20", "2026-09-26"))


def failed_cal() -> CalendarSnapshot:
    return CalendarSnapshot(events=[], fetched=False, error="خطای شبکه در دریافت تقویم")


def good_news() -> NewsSnapshot:
    """اخبار در جهت خرید EURUSD."""
    return NewsSnapshot(items=[
        NewsItem(title="Euro rallies as ECB turns hawkish", score=5,
                 direction={"EUR": 1, "USD": -1}, source="FXStreet",
                 published=WED_OVERLAP - timedelta(hours=2), keywords=["رالی"]),
        NewsItem(title="Dollar slides on soft US data", score=5,
                 direction={"USD": -1}, source="ForexLive",
                 published=WED_OVERLAP - timedelta(hours=1)),
    ], fetched_at=WED_OVERLAP, feeds_ok=2)


def sell_news() -> NewsSnapshot:
    """اخبار در جهت فروش EURUSD."""
    return NewsSnapshot(items=[
        NewsItem(title="Dollar rallies as Fed turns hawkish", score=5,
                 direction={"EUR": -1, "USD": 1}, source="FXStreet",
                 published=WED_OVERLAP - timedelta(hours=2)),
    ], fetched_at=WED_OVERLAP, feeds_ok=1)


def contra_news() -> NewsSnapshot:
    """اخبار خلافِ جهت خرید EURUSD → ⚠️."""
    return NewsSnapshot(items=[
        NewsItem(title="Euro falls as ECB signals rate cuts", score=5,
                 direction={"EUR": -1, "USD": 1}, source="FXStreet",
                 published=WED_OVERLAP - timedelta(hours=1)),
    ], fetched_at=WED_OVERLAP, feeds_ok=1)


def neutral_news() -> NewsSnapshot:
    """خبرِ بی‌ربط به EURUSD → خنثی."""
    return NewsSnapshot(items=[
        NewsItem(title="RBA holds rates steady", score=5,
                 direction={"AUD": 1}, source="ForexLive",
                 published=WED_OVERLAP - timedelta(hours=1)),
    ], fetched_at=WED_OVERLAP, feeds_ok=1)


def breaking_news() -> NewsSnapshot:
    """خبر فوری مرتبط با EUR → وتوی BREAKING_NEWS."""
    return NewsSnapshot(items=[NewsItem(
        title="BREAKING: ECB surprise decision", score=6,
        direction={"EUR": -1, "USD": 1}, breaking=True,
        source="ForexLive", published=WED_OVERLAP)],
        fetched_at=WED_OVERLAP, feeds_ok=1)


# ══════════════════════════════════════════════════════════════
#  سریال‌سازی (آینهٔ judgment_dump در tests/js/gen_fixtures.py)
# ══════════════════════════════════════════════════════════════
def evidence_dump(e) -> dict:
    return {"key": e.key, "label_fa": e.label_fa, "points": e.points,
            "max_points": e.max_points, "detail_fa": e.detail_fa,
            "ok": e.ok, "unavailable": e.unavailable, "icon": e.icon}


def veto_dump(v) -> dict:
    return {"key": v.key, "title_fa": v.title_fa, "detail_fa": v.detail_fa}


def signal_dump(s) -> dict:
    return {"symbol": s.symbol, "fa_name": s.fa_name, "direction": s.direction,
            "sid": s.sid, "score": s.score, "max_score": s.max_score, "stars": s.stars,
            "entry": s.entry, "sl": s.sl, "tp": s.tp, "pip": s.pip, "atr": s.atr,
            "risk_pips": s.risk_pips, "reward_pips": s.reward_pips, "rr": s.rr,
            "is_gold": s.is_gold, "session_fa": s.session_fa,
            "now": s.now.isoformat(), "warnings": s.warnings, "sl_capped": s.sl_capped,
            "direction_fa": s.direction_fa, "journal": s.to_journal(sent=True)}


def judgment_dump(j) -> dict:
    return {"symbol": j.symbol, "fa_name": j.fa_name, "direction": j.direction,
            "score": j.score, "max_score": j.max_score,
            "reject_reason": j.reject_reason, "reject_detail": j.reject_detail,
            "status_fa": j.status_fa, "price": j.price, "pip": j.pip,
            "vetoes": [veto_dump(v) for v in j.vetoes],
            "evidences": [evidence_dump(e) for e in j.evidences],
            "warnings": j.warnings,
            "signal": signal_dump(j.signal) if j.signal else None}


def _judge(a, md=None, ctx=None, jfn=None) -> dict:
    fn = judge_symbol if jfn is None else jfn
    return judgment_dump(fn(a, {}, md if md is not None else make_md(),
                            ctx if ctx is not None else make_ctx()))


# ══════════════════════════════════════════════════════════════
#  گروه ۱ — وتوها
# ══════════════════════════════════════════════════════════════
def battery_veto_single(jfn=None) -> dict:
    """هر وتو به‌تنهایی — بقیهٔ دروازه‌ها خاموش/دور نگه داشته شده‌اند."""
    out = {}
    out["DATA"] = _judge(make_analysis(verdict="DATA"),
                         ctx=make_ctx(cal=clean_cal(), news=good_news()), jfn=jfn)
    out["WEEKEND"] = _judge(make_analysis(),
                            ctx=make_ctx(now=SAT, cal=clean_cal(), news=good_news()),
                            jfn=jfn)
    out["TF_CONFLICT"] = _judge(make_analysis(h1_agrees=False),
                                ctx=make_ctx(cal=clean_cal(), news=good_news()),
                                jfn=jfn)
    out["RANGE"] = _judge(make_analysis(adx=14.0),
                          ctx=make_ctx(cal=clean_cal(), news=good_news()), jfn=jfn)
    out["EVENT"] = _judge(make_analysis(),
                          ctx=make_ctx(cal=near_cal(WED_OVERLAP), news=good_news()),
                          jfn=jfn)
    out["VOL_SPIKE"] = _judge(make_analysis(), md=make_md(last_spike=9.0),
                              ctx=make_ctx(cal=clean_cal(), news=good_news()),
                              jfn=jfn)
    out["BREAKING_NEWS"] = _judge(make_analysis(),
                                  ctx=make_ctx(cal=clean_cal(), news=breaking_news()),
                                  jfn=jfn)
    return out


def battery_veto_multi(jfn=None) -> dict:
    """چند وتوی هم‌زمان — ترتیب ارزیابیِ امروز پین می‌شود.

    نکته: TF_CONFLICT و RANGE با گارد `verdict != "DATA"` رد می‌شوند، پس
    «همهٔ ۷ تا با هم» غیرممکن است — دو ترکیبِ بیشینه پین می‌شوند.
    """
    spiky = make_md(last_spike=9.0)
    out = {}
    out["all_except_data"] = _judge(
        make_analysis(h1_agrees=False, adx=14.0), md=spiky,
        ctx=make_ctx(now=SAT, cal=near_cal(SAT), news=breaking_news()), jfn=jfn)
    out["with_data"] = _judge(
        make_analysis(verdict="DATA", h1_agrees=False, adx=14.0), md=spiky,
        ctx=make_ctx(now=SAT, cal=near_cal(SAT), news=breaking_news()), jfn=jfn)
    return out


def battery_veto_toggles(jfn=None) -> dict:
    """کلیدهای *موجود* config — خاموش‌کردن یک دروازه فقط همان را برمی‌دارد."""
    out = {}
    veto_no_weekend = {**JCFG["veto"], "weekend": False}
    out["weekend_off_saturday"] = _judge(
        make_analysis(),
        ctx=make_ctx(now=SAT, cal=clean_cal(), news=good_news(),
                     veto=veto_no_weekend), jfn=jfn)
    veto_no_range = {**JCFG["veto"], "range_market": False}
    out["range_off_low_adx"] = _judge(
        make_analysis(adx=14.0),
        ctx=make_ctx(cal=clean_cal(), news=good_news(), veto=veto_no_range),
        jfn=jfn)
    return out


def battery_veto_clean() -> list:
    """ستاپ سالم — هیچ وتویی فعال نیست (خروجی مستقیم collect_vetoes)."""
    vs = collect_vetoes(make_analysis(), {}, make_md(),
                        make_ctx(cal=clean_cal(), news=good_news()))
    return [veto_dump(v) for v in vs]


# ══════════════════════════════════════════════════════════════
#  گروه ۲ — هر ۸ شاهد، همهٔ شاخه‌ها (فراخوانی مستقیم توابع ev_*)
# ══════════════════════════════════════════════════════════════
def battery_evidence() -> dict:
    out = {}
    d = "BUY"

    def rec(name, e):
        out[name] = evidence_dump(e)

    # ── trend ──
    ctx = make_ctx(cal=clean_cal(), news=good_news())
    rec("trend_strong", ev_trend(make_analysis(adx=32.0), ctx, d))
    rec("trend_medium", ev_trend(make_analysis(adx=22.0), ctx, d))

    # ── level ──
    rec("level_buy_close", ev_level(make_analysis(support=1.1486), ctx, "BUY"))
    rec("level_buy_near", ev_level(make_analysis(support=1.1480), ctx, "BUY"))
    rec("level_buy_far", ev_level(make_analysis(support=1.1400), ctx, "BUY"))
    rec("level_buy_unavailable", ev_level(make_analysis(support=None), ctx, "BUY"))
    rec("level_sell_close", ev_level(make_analysis(resistance=1.1494), ctx, "SELL"))

    # ── fundamental ──
    rec("fund_clean", ev_fundamental(make_analysis(),
                                     make_ctx(cal=clean_cal()), d))
    rec("fund_high_soon", ev_fundamental(make_analysis(),
                                         make_ctx(cal=high_soon_cal(WED_OVERLAP)), d))
    rec("fund_med_soon", ev_fundamental(make_analysis(),
                                        make_ctx(cal=med_soon_cal(WED_OVERLAP)), d))
    rec("fund_cal_failed", ev_fundamental(make_analysis(),
                                          make_ctx(cal=failed_cal()), d))
    rec("fund_cal_off", ev_fundamental(make_analysis(), make_ctx(cal=None), d))

    # ── momentum ──
    rec("mom_buy_confirm", ev_momentum(make_analysis(rsi=38.0, rsi_rising=True), ctx, "BUY"))
    rec("mom_buy_oversold", ev_momentum(make_analysis(rsi=25.0, rsi_rising=True), ctx, "BUY"))
    rec("mom_buy_high", ev_momentum(make_analysis(rsi=55.0, rsi_rising=True), ctx, "BUY"))
    rec("mom_buy_not_rising", ev_momentum(make_analysis(rsi=38.0, rsi_rising=False), ctx, "BUY"))
    rec("mom_sell_confirm", ev_momentum(make_analysis(rsi=62.0, rsi_rising=False), ctx, "SELL"))
    rec("mom_sell_overbought", ev_momentum(make_analysis(rsi=75.0, rsi_rising=False), ctx, "SELL"))
    rec("mom_sell_low", ev_momentum(make_analysis(rsi=45.0, rsi_rising=False), ctx, "SELL"))

    # ── strength ──
    rec("str_buy_aligned", ev_strength(make_analysis(),
                                       make_ctx(ranking=RANK_DEFAULT), "BUY"))
    rec("str_buy_contra", ev_strength(make_analysis(),
                                      make_ctx(ranking=RANK_USD_STRONG), "BUY"))
    rec("str_sell_aligned", ev_strength(make_analysis(),
                                        make_ctx(ranking=RANK_USD_STRONG), "SELL"))
    rec("str_empty", ev_strength(make_analysis(), make_ctx(ranking=[]), "BUY"))
    rec("str_missing", ev_strength(make_analysis(),
                                   make_ctx(ranking=[("GBP", 0.1), ("USD", -0.2)]), "BUY"))

    # ── news ──
    rec("news_supports", ev_news(make_analysis(), make_ctx(news=good_news()), "BUY"))
    rec("news_supports_sell", ev_news(make_analysis(), make_ctx(news=sell_news()), "SELL"))
    rec("news_contra", ev_news(make_analysis(), make_ctx(news=contra_news()), "BUY"))
    rec("news_neutral", ev_news(make_analysis(), make_ctx(news=neutral_news()), "BUY"))
    rec("news_unavailable", ev_news(make_analysis(), make_ctx(news=None), "BUY"))

    # ── tradingview ──
    rec("tv_match_buy", ev_tradingview(make_analysis(), make_ctx(tv=TV_BUY), "BUY"))
    rec("tv_match_sell", ev_tradingview(make_analysis(), make_ctx(tv=TV_SELL), "SELL"))
    rec("tv_neutral", ev_tradingview(make_analysis(), make_ctx(tv=TV_NEUTRAL), "BUY"))
    rec("tv_opposite", ev_tradingview(make_analysis(), make_ctx(tv=TV_SELL), "BUY"))
    rec("tv_unavailable", ev_tradingview(make_analysis(), make_ctx(tv={}), "BUY"))

    # ── session ──
    rec("sess_overlap", ev_session(make_ctx(now=WED_OVERLAP)))
    rec("sess_liquid", ev_session(make_ctx(now=WED_LONDON)))
    rec("sess_thin", ev_session(make_ctx(now=WED_THIN)))
    rec("sess_closed", ev_session(make_ctx(now=SAT)))
    return out


# ══════════════════════════════════════════════════════════════
#  گروه ۳ — داوری کامل (judge_symbol / judge_all)
# ══════════════════════════════════════════════════════════════
def battery_judge_full(jfn=None) -> dict:
    out = {}
    # BUY طلایی — همهٔ مدارک حاضر → ۱۱/۱۱
    out["buy"] = _judge(make_analysis(), md=make_md(),
                        ctx=make_ctx(cal=clean_cal(), news=good_news()), jfn=jfn)
    # SELL طلایی — ۱۱/۱۱
    out["sell"] = _judge(
        make_analysis(trend="bearish", rsi=62.0, rsi_rising=False,
                      verdict="SELL_SETUP", support=1.1400, resistance=1.1494),
        md=make_md(),
        ctx=make_ctx(cal=clean_cal(), news=sell_news(),
                     ranking=RANK_USD_STRONG, tv=TV_SELL), jfn=jfn)
    return out


def battery_judge_low_score(jfn=None) -> dict:
    """امتیاز ۵ از ۱۱ → LOW_SCORE + دو هشدار ⚠️ (خبر و TV خلاف جهت)."""
    return {"low_score": _judge(
        make_analysis(rsi=55.0, support=1.1400),
        md=make_md(),
        ctx=make_ctx(cal=clean_cal(), news=contra_news(),
                     ranking=RANK_USD_STRONG, tv=TV_SELL), jfn=jfn)}


def battery_judge_no_setup(jfn=None) -> dict:
    """هر ۵ شاخهٔ «ستاپی شکل نگرفته» — با گاردهای وتو که لازم است خاموش."""
    out = {}
    base_ctx = dict(cal=clean_cal(), news=good_news())
    out["trend_none"] = _judge(make_analysis(trend="none", verdict="WAIT"),
                               ctx=make_ctx(**base_ctx), jfn=jfn)
    out["h1_disagree"] = _judge(
        make_analysis(h1_agrees=False, verdict="WAIT"),
        ctx=make_ctx(veto={**JCFG["veto"], "timeframe_conflict": False}, **base_ctx),
        jfn=jfn)
    out["range_no_veto"] = _judge(
        make_analysis(adx=14.0, verdict="WAIT"),
        ctx=make_ctx(veto={**JCFG["veto"], "range_market": False}, **base_ctx),
        jfn=jfn)
    out["bullish_rsi_high"] = _judge(make_analysis(rsi=55.0, verdict="WAIT"),
                                     ctx=make_ctx(**base_ctx), jfn=jfn)
    out["bearish_rsi_low"] = _judge(
        make_analysis(trend="bearish", rsi=40.0, verdict="WAIT"),
        ctx=make_ctx(**base_ctx), jfn=jfn)
    return out


def battery_judge_capped(jall=None) -> list:
    """سه سیگنال آماده، سقف ۱ → بهترین می‌ماند، بقیه CAPPED."""
    a1 = make_analysis()                                             # ۱۱/۱۱
    a2 = make_analysis(symbol="GBPUSD", fa_name="پوند به دلار آمریکا",
                       base="GBP", quote="USD", price=1.3500,
                       support=1.3496, resistance=1.3560)           # ۱۰/۱۱ (بدون TV)
    a3 = make_analysis(symbol="USDJPY", fa_name="دلار به ین ژاپن",
                       base="USD", quote="JPY", price=150.00, pip=0.01,
                       atr=0.10, support=149.96, resistance=150.60,
                       rsi=55.0)                                    # ۸/۱۱
    ctx = make_ctx(cal=clean_cal(), news=good_news(), max_signals_per_cycle=1)
    fn = judge_all if jall is None else jall
    return [judgment_dump(j) for j in fn([a1, a2, a3], {}, ctx)]


def battery_judge_all_mixed(jall=None) -> list:
    """judge_all با ۴ نماد در ۴ سرنوشت: سیگنال / وتو / بدون ستاپ / امتیاز کم."""
    a1 = make_analysis()                                             # BUY ۱۰/۱۱ (بدون خبر)
    a2 = make_analysis(symbol="GBPUSD", fa_name="پوند به دلار آمریکا",
                       base="GBP", quote="USD", price=1.3500, adx=14.0,
                       support=1.3496, resistance=1.3560)            # VETO (RANGE)
    a3 = make_analysis(symbol="USDJPY", fa_name="دلار به ین ژاپن",
                       base="USD", quote="JPY", price=150.00, pip=0.01,
                       atr=0.10, trend="none", verdict="WAIT",
                       support=149.96, resistance=150.60)            # NO_SETUP
    a4 = make_analysis(symbol="AUDUSD", fa_name="دلار استرالیا به دلار آمریکا",
                       base="AUD", quote="USD", price=0.6600, rsi=55.0,
                       support=0.6500, resistance=0.6700)            # LOW_SCORE (۵/۱۱)
    ctx = make_ctx(cal=clean_cal(), news=None)
    fn = judge_all if jall is None else jall
    return [judgment_dump(j) for j in fn([a1, a2, a3, a4], {}, ctx)]


def battery_risk_math() -> dict:
    """ریاضی SL/TP — همان شش حالتِ selftest/test_judge با dump کامل."""
    rc = judge_config(CFG)["risk"]
    cases = {
        "buy_level": ("BUY", 1.1490, 0.0010, 1.1486, 1.1560),
        "sell_level": ("SELL", 1.1490, 0.0010, 1.1440, 1.1495),
        "buy_no_level": ("BUY", 1.1490, 0.0010, None, None),
        "buy_far_capped": ("BUY", 1.1490, 0.0010, 1.1400, None),
        "buy_tight_floor": ("BUY", 1.1490, 0.0010, 1.14895, None),
        "atr_zero_guard": ("BUY", 1.1490, 0.0, 1.1486, 1.1560),
    }
    out = {}
    for name, args in cases.items():
        sl, tp, risk, capped = compute_levels(*args, rc)
        out[name] = {"sl": sl, "tp": tp, "risk": risk, "capped": capped}
    return out


# ══════════════════════════════════════════════════════════════
def build_battery(judge_symbol_fn=None, judge_all_fn=None) -> dict:
    """کل باتری — خروجی کاملاً قطعی (بدون شبکه، بدون ساعت سیستم).

    judge_symbol_fn/judge_all_fn: تزریق *اختیاری* مسیر داوری (پیش‌فرض =
    توابع مستقیم scoring). برای طلاییِ مسیر rule-plugin در test_plugins.
    گروه‌های veto_clean/evidence_branches/risk_math عمداً همیشه مستقیم‌اند —
    parity آن‌ها با goldenهای «adapter == فراخوانی مستقیم» پوشش داده می‌شود.
    """
    return {
        "veto_single": battery_veto_single(judge_symbol_fn),
        "veto_multi": battery_veto_multi(judge_symbol_fn),
        "veto_toggles": battery_veto_toggles(judge_symbol_fn),
        "veto_clean": battery_veto_clean(),
        "evidence_branches": battery_evidence(),
        "judge_full": battery_judge_full(judge_symbol_fn),
        "judge_low_score": battery_judge_low_score(judge_symbol_fn),
        "judge_no_setup": battery_judge_no_setup(judge_symbol_fn),
        "judge_capped": battery_judge_capped(judge_all_fn),
        "judge_all_mixed": battery_judge_all_mixed(judge_all_fn),
        "risk_math": battery_risk_math(),
    }


def main() -> int:
    battery = build_battery()
    GOLDEN_PATH.write_text(
        json.dumps(battery, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8")
    n_veto = len(battery["veto_single"]) + len(battery["veto_multi"]) + \
        len(battery["veto_toggles"]) + 1
    n_ev = len(battery["evidence_branches"])
    n_j = (len(battery["judge_full"]) + len(battery["judge_low_score"])
           + len(battery["judge_no_setup"]) + len(battery["judge_capped"])
           + len(battery["judge_all_mixed"]))
    print(f"✅ طلاییِ داور ضبط شد — {GOLDEN_PATH.name}: "
          f"{n_veto} سناریوی وتو + {n_ev} شاخهٔ شاهد + {n_j} داوری کامل "
          f"+ {len(battery['risk_math'])} حالت ریاضی ریسک")
    return 0


if __name__ == "__main__":
    sys.exit(main())
