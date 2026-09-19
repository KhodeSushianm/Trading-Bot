# -*- coding: utf-8 -*-
"""تست جامع داور امتیازدهی (مرحله ۳) — کاملاً آفلاین و قطعی.

همهٔ مسیرها با دادهٔ مصنوعی و `now` تزریق‌شده سنجیده می‌شوند، چون بازار
در آخر هفته بسته است و وتوی WEEKEND همه‌چیز را می‌بلعد.
"""
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from src.analysis.technical import SymbolAnalysis
from src.data.base import MarketData
from src.fundamental.calendar import CalendarEvent, CalendarSnapshot
from src.fundamental.news import NewsItem, NewsSnapshot
from src.data.tradingview import TVSnapshot
from src.judge.scoring import JudgeContext, compute_levels, judge_symbol, judge_all
from src.judge.session import market_status
from src.report.signal import render_judge_summary, render_signal
from src.config import load_config

FAILS = []
WED_OVERLAP = datetime(2026, 9, 23, 14, 0, tzinfo=timezone.utc)   # چهارشنبه، هم‌پوشانی لندن/NY
SAT = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)           # شنبه — بازار بسته
CFG = load_config()
ACFG = CFG["analysis"]
JCFG = CFG["judge"]
SYMS = CFG["symbols"]


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


def make_md(n=300, base=1.1490, atr=0.0010, seed=7, last_spike=1.0):
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
    return MarketData(symbol="EURUSD", m15=m15, h1=h1, h4=h4)


def make_analysis(**kw):
    d = dict(symbol="EURUSD", fa_name="یورو به دلار آمریکا", base="EUR", quote="USD",
             price=1.1490, pip=0.0001, trend="bullish", h1_agrees=True, adx=32.0,
             rsi=38.0, rsi_rising=True, atr=0.0010, support=1.1486, resistance=1.1560,
             last_candle=WED_OVERLAP, verdict="BUY_SETUP")
    d.update(kw)
    return SymbolAnalysis(**d)


def make_ctx(now=WED_OVERLAP, cal=None, news=None, ranking=None, tv=None, **jover):
    jcfg = dict(JCFG)
    jcfg.update(jover)
    return JudgeContext(jcfg=jcfg, acfg=ACFG, symbols_cfg=SYMS,
                        ranking=ranking if ranking is not None else [
                            ("EUR", 0.30), ("GBP", 0.10), ("USD", -0.20), ("JPY", -0.40)],
                        tv_map=tv if tv is not None else {
                            "EURUSD": TVSnapshot("EURUSD", 1.149, 41.0, 32.0, "BUY", 13, 4, 9)},
                        cal_snap=cal, news_snap=news, now=now,
                        status=market_status(now), event_veto_minutes=30.0)


def clean_cal():
    """تقویمی با رویدادهای دور (پس پنجرهٔ فاندامنتال پاک است)."""
    return CalendarSnapshot(events=[CalendarEvent(
        when=WED_OVERLAP + timedelta(days=4), country="USD", title="CPI y/y",
        title_fa="تورم سالانه", impact="HIGH", forecast="2.1%", previous="2.0%",
        category="تورم", polarity=1)], fetched=True, week_range=("2026-09-20", "2026-09-26"))


def good_news():
    return NewsSnapshot(items=[
        NewsItem(title="Euro rallies as ECB turns hawkish", score=5,
                 direction={"EUR": 1, "USD": -1}, source="FXStreet",
                 published=WED_OVERLAP - timedelta(hours=2), keywords=["رالی"]),
        NewsItem(title="Dollar slides on soft US data", score=5,
                 direction={"USD": -1}, source="ForexLive",
                 published=WED_OVERLAP - timedelta(hours=1)),
    ], fetched_at=WED_OVERLAP, feeds_ok=2)


print("=" * 78)
print("۱) مسیر طلایی: همهٔ مدارک حاضرند → سیگنال صادر می‌شود")
print("=" * 78)
a = make_analysis()
j = judge_symbol(a, {}, make_md(), make_ctx(cal=clean_cal(), news=good_news()))
check(j.signal is not None, f"سیگنال صادر شد (score={j.score}/{j.max_score}, vetoes={[v.key for v in j.vetoes]})")
if j.signal:
    s = j.signal
    check(s.direction == "BUY", f"جهت = {s.direction}")
    check(s.max_score == 11, f"حداکثر امتیاز = {s.max_score} (باید ۱۱ باشد)")
    check(s.score >= 7, f"امتیاز {s.score} ≥ آستانه ۷")
    check(s.sl < s.entry < s.tp, f"BUY: SL {s.sl:.5f} < ورود {s.entry:.5f} < TP {s.tp:.5f}")
    check(abs(s.rr - 2.0) < 1e-9, f"نسبت سود/ریسک = {s.rr}")
    check(abs(s.reward_pips - 2 * s.risk_pips) < 0.6,
          f"هدف = ۲ برابر ریسک ({s.risk_pips:.0f} → {s.reward_pips:.0f} پیپ)")
    check(s.stars >= 1 and s.stars <= 5, f"ستاره‌ها = {s.stars}")
    check(s.session_fa.count("هم‌پوشانی") == 1, f"سشنِ هم‌پوشانی تشخیص داده شد: {s.session_fa}")
    print("     امتیازها: " + ", ".join(f"{e.key}={e.points}/{e.max_points}" for e in s.evidences))

print()
print("۲) متن پیام سیگنال")
txt = render_signal(j.signal)
print("─" * 78)
print(txt)
print("─" * 78)
check("سیگنال خرید" in txt, "عنوان سیگنال خرید")
check("پشتوانه:" in txt and "از ۱۱" in txt, "امتیاز با مخرج درست و ارقام فارسی")
check("📍 ورود" in txt and "🛑 حد ضرر" in txt and "🎯 هدف" in txt, "سه قیمت کلیدی حاضرند")
check("ریسک پیشنهادی" in txt, "یادآوری ریسک ۱٪")
check("مدارکی که امتیاز نگرفتند" in txt or all(e.points > 0 for e in j.signal.evidences),
      "مدارک ناموفق هم شفاف فهرست می‌شوند")
check("نه دستور معامله" in txt, "سلب مسئولیت در پیام هست")
# ارقام فارسی در بخش‌های روایی، لاتین در قیمت‌ها (قرارداد src/fa.py)
head = txt.split("پشتوانه:")[1].split("\n")[0]
check(head.strip() == "۱۱ از ۱۱", f"امتیاز با ارقام فارسی: «{head.strip()}»")
check("1.14900" in txt, "قیمت‌ها لاتین می‌مانند (برای تایپ در متاتریدر)")
check("پنجرهٔ فاندامنتال پاک" in txt and "واکنش به سطح کلیدی" in txt,
      "مدرک‌ها با نام فارسی چاپ می‌شوند")
check(txt.count("نه دستور معامله") == 1,
      "سلب مسئولیت دقیقاً یک‌بار آمده (نه تکراری)")

print()
print("=" * 78)
print("۳) دروازه‌های وتو — هرکدام باید جداگانه سیگنال را متوقف کنند")
print("=" * 78)
CASES = [
    ("WEEKEND", dict(now=SAT), dict(),
     "شنبه — بازار بسته"),
    ("TF_CONFLICT", dict(), dict(h1_agrees=False),
     "تضاد تایم‌فریم"),
    ("RANGE", dict(), dict(adx=14.0),
     "ADX زیر آستانه"),
    ("DATA", dict(), dict(verdict="DATA"),
     "دادهٔ ناکافی"),
    ("VOL_SPIKE", dict(md=make_md(last_spike=9.0)), dict(),
     "جهش نوسان"),
]
for key, ctxkw, akw, label in CASES:
    md = ctxkw.pop("md", make_md())
    aa = make_analysis(**akw)
    jj = judge_symbol(aa, {}, md, make_ctx(cal=clean_cal(), news=good_news(), **ctxkw))
    keys = [v.key for v in jj.vetoes]
    check(jj.signal is None and key in keys, f"{label}: وتوی {key} فعال (vetoes={keys})")
    check(jj.reject_reason == "VETO", f"   → reject_reason={jj.reject_reason}")

# وتوی رویداد پراثر نزدیک
near_cal = CalendarSnapshot(events=[CalendarEvent(
    when=WED_OVERLAP + timedelta(minutes=12), country="USD", title="Federal Funds Rate",
    title_fa="نرخ بهره فدرال رزرو", impact="HIGH", forecast="4.00%", previous="3.75%")],
    fetched=True, week_range=("2026-09-20", "2026-09-26"))
jj = judge_symbol(make_analysis(), {}, make_md(), make_ctx(cal=near_cal, news=good_news()))
check(jj.signal is None and "EVENT" in [v.key for v in jj.vetoes],
      f"رویداد پراثر ۱۲ دقیقه دیگر → وتوی EVENT ({[v.key for v in jj.vetoes]})")

# وتوی خبر فوری
brk = NewsSnapshot(items=[NewsItem(title="BREAKING: ECB surprise decision", score=6,
                                   direction={"EUR": -1, "USD": 1}, breaking=True,
                                   source="ForexLive", published=WED_OVERLAP)],
                   fetched_at=WED_OVERLAP, feeds_ok=1)
jj = judge_symbol(make_analysis(), {}, make_md(), make_ctx(cal=clean_cal(), news=brk))
check(jj.signal is None and "BREAKING_NEWS" in [v.key for v in jj.vetoes],
      f"خبر فوری → وتوی BREAKING_NEWS ({[v.key for v in jj.vetoes]})")

# خاموش‌کردن یک وتو از طریق config باید واقعاً اثر کند
jj = judge_symbol(make_analysis(), {}, make_md(),
                  make_ctx(cal=clean_cal(), news=good_news(), now=SAT,
                           veto={**JCFG["veto"], "weekend": False}))
check("WEEKEND" not in [v.key for v in jj.vetoes],
      "با veto.weekend=false وتوی آخر هفته اعمال نمی‌شود (تنظیم‌پذیر است)")

print()
print("=" * 78)
print("۴) امتیاز ناکافی → سیگنال نیست، ولی دلیل شفاف است")
print("=" * 78)
# همهٔ مدارک جانبی را از بین ببر: تقویم خراب، اخبار خراب، TV مخالف، سشن ضعیف، رتبهٔ ارز وارونه
bad = JudgeContext(jcfg=JCFG, acfg=ACFG, symbols_cfg=SYMS,
                   ranking=[("USD", 0.40), ("JPY", 0.2), ("GBP", 0.0), ("EUR", -0.30)],
                   tv_map={"EURUSD": TVSnapshot("EURUSD", 1.149, 62.0, 32.0, "SELL", 3, 14, 9)},
                   cal_snap=CalendarSnapshot(error="timeout"), news_snap=NewsSnapshot(error="down"),
                   now=datetime(2026, 9, 23, 3, 0, tzinfo=timezone.utc),   # سشن توکیو
                   status=market_status(datetime(2026, 9, 23, 3, 0, tzinfo=timezone.utc)),
                   event_veto_minutes=30.0)
jj = judge_symbol(make_analysis(), {}, make_md(), bad)
check(jj.signal is None, f"سیگنال صادر نشد (امتیاز {jj.score}/{jj.max_score})")
check(jj.reject_reason == "LOW_SCORE", f"reject_reason = {jj.reject_reason}")
check(jj.score < 7, f"امتیاز {jj.score} زیر آستانهٔ ۷")
check(all(e.points == 0 for e in jj.evidences if e.key in ("fundamental", "news", "tv", "session", "strength")),
      "مدارکِ داده‌نیافته واقعاً صفر گرفتند (امتیاز باد نکرد)")
check(any(e.unavailable for e in jj.evidences),
      "مدارکِ «داده در دسترس نبود» علامت unavailable خوردند (نه اینکه صفرِ بی‌دلیل بگیرند)")
print(f"     جزئیات: {jj.reject_detail}")
for e in jj.evidences:
    print(f"       {e.icon} {e.key:12s} {e.points}/{e.max_points} — {e.detail_fa[:66]}")

print()
print("=" * 78)
print("۵) ریاضی حد ضرر و هدف")
print("=" * 78)
rc = JCFG["risk"]
# خرید با حمایت نزدیک → SL زیر حمایت
sl, tp, risk, capped = compute_levels("BUY", 1.1490, 0.0010, 1.1486, 1.1560, rc)
check(sl < 1.1486, f"SL خرید زیر حمایت است ({sl:.5f} < 1.1486)")
check(tp > 1.1490, f"TP بالای ورود است ({tp:.5f})")
check(abs((tp - 1.1490) / (1.1490 - sl) - 2.0) < 1e-6, "نسبت دقیقاً ۲ است")
check(not capped, "سقف ATR فعال نشد")
# فروش با مقاومت
sl2, tp2, risk2, _ = compute_levels("SELL", 1.1490, 0.0010, 1.1440, 1.1495, rc)
check(sl2 > 1.1495 and tp2 < 1.1490, f"SELL: SL {sl2:.5f} بالای مقاومت، TP {tp2:.5f} زیر ورود")
# نبود سطح → fallback بر پایهٔ ATR
sl3, _, risk3, _ = compute_levels("BUY", 1.1490, 0.0010, None, None, rc)
check(abs(risk3 - 1.5 * 0.0010) < 1e-9, f"بدون سطح: ریسک = ۱٫۵×ATR ({risk3 / 0.0010:.2f}×ATR)")
# سطح خیلی دور → سقف max_sl_atr
sl4, _, risk4, capped4 = compute_levels("BUY", 1.1490, 0.0010, 1.1400, None, rc)
check(capped4 and abs(risk4 - 3.0 * 0.0010) < 1e-9,
      f"سطح دور → SL به سقف ۳×ATR محدود شد (capped={capped4}, risk={risk4/0.0010:.1f}×ATR)")
# سطح خیلی نزدیک → کف min_sl_atr
sl5, _, risk5, _ = compute_levels("BUY", 1.1490, 0.0010, 1.14895, None, rc)
check(abs(risk5 - 0.6 * 0.0010) < 1e-9, f"سطح چسبیده → SL به کف ۰٫۶×ATR رسید ({risk5/0.0010:.2f}×ATR)")
check(all(x == x for x in (sl, tp)), "NaN تولید نشد")

print()
print("=" * 78)
print("۶) سقف تعداد سیگنال در هر چرخه")
print("=" * 78)
ctx = make_ctx(cal=clean_cal(), news=good_news())
many = [make_analysis(symbol="EURUSD"), make_analysis(symbol="GBPUSD", base="GBP", quote="USD"),
        make_analysis(symbol="AUDUSD", base="AUD", quote="USD", adx=21.0),
        make_analysis(symbol="USDJPY", base="USD", quote="JPY", verdict="WAIT", adx=15.0)]
mkt = {"EURUSD": make_md(), "GBPUSD": make_md(), "AUDUSD": make_md(), "USDJPY": make_md()}
res = judge_all(many, mkt, ctx)
n_sig = sum(1 for r in res if r.signal)
check(n_sig <= 3, f"با سقف پیش‌فرض ۳ → {n_sig} سیگنال صادر شد")

# حالا سقف را روی ۱ بگذار تا مسیر CAPPED واقعاً اجرا شود
ctx2 = make_ctx(cal=clean_cal(), news=good_news(), max_signals_per_cycle=1)
res2 = judge_all(many, mkt, ctx2)
sig2 = [r for r in res2 if r.signal]
cap2 = [r for r in res2 if r.reject_reason == "CAPPED"]
check(len(sig2) == 1, f"با سقف ۱ → دقیقاً ۱ سیگنال ({len(sig2)})")
check(len(cap2) == 2, f"دو سیگنالِ واجدشرایط دیگر «به سقف خورد» علامت گرفتند ({len(cap2)})")
check(sig2 and sig2[0].score == max(r.score for r in res if r.signal),
      f"بهترین سیگنال نگه داشته شد ({sig2[0].symbol} با {sig2[0].score} امتیاز)، نه اولین")
check(all(r.reject_detail for r in cap2), "سیگنالِ به‌سقف‌خورده هم دلیل دارد (بی‌صدا حذف نشد)")

for r in res2:
    print(f"     {r.symbol:<8} {r.status_fa:<24} score={r.score}/{r.max_score} "
          f"reason={r.reject_reason or '—'}")

print()
print("=" * 78)
print("۷) خلاصهٔ داور در گزارش — «چرا سیگنال ندادیم» هم باید باشد")
print("=" * 78)
summary = render_judge_summary(res, min_score=7, now=WED_OVERLAP)
print("─" * 78)
print(summary)
print("─" * 78)
check("⚖️ داور امتیازدهی" in summary, "عنوان بخش داور")
check("سرنوشت بقیهٔ نمادها" in summary, "نمادهای ردشده هم فهرست می‌شوند")
check("USDJPY" in summary, "نماد بدون ستاپ هم ذکر شده")

empty = render_judge_summary([judge_symbol(make_analysis(verdict="WAIT", adx=15.0), {},
                                           make_md(), ctx)], min_score=7)
check("هیچ سیگنالی صادر نشد" in empty, "وقتی سیگنالی نیست، صادقانه گفته می‌شود")
check("وعده" in empty or "پشتوانه" in empty, "یادآوری وعدهٔ سیستم در حالت بدون سیگنال")

print()
print("=" * 78)
print("۸) جلوگیری از اسپم: سیگنال تکراری در cooldown دوباره ارسال نمی‌شود")
print("=" * 78)
from src.engine import should_send_signal  # noqa: E402

sig = j.signal
state = {}
go, why = should_send_signal(state, sig, JCFG, now=WED_OVERLAP)
check(go, "بار اول → ارسال می‌شود")

state[f"{sig.symbol}|{sig.direction}"] = {"ts": WED_OVERLAP.isoformat(), "score": sig.score}
go, why = should_send_signal(state, sig, JCFG, now=WED_OVERLAP + timedelta(minutes=15))
check(not go, f"۱۵ دقیقه بعد، همان سیگنال → ارسال نمی‌شود ({why[:60]})")

go, _ = should_send_signal(state, sig, JCFG,
                           now=WED_OVERLAP + timedelta(minutes=JCFG["resend_cooldown_minutes"] + 1))
check(go, "بعد از پایان cooldown → دوباره ارسال می‌شود")

# امتیاز بهتر شده → حتی داخل cooldown هم می‌رود
better = type(sig)(**{**sig.__dict__, "score": sig.score + JCFG["resend_score_gain"]})
go, why = should_send_signal(state, better, JCFG, now=WED_OVERLAP + timedelta(minutes=20))
check(go, f"امتیاز {JCFG['resend_score_gain']} واحد بهتر شد → داخل cooldown هم ارسال می‌شود ({why[:40]})")

# جهت مخالف، سیگنال جداست
opp = type(sig)(**{**sig.__dict__, "direction": "SELL"})
go, _ = should_send_signal(state, opp, JCFG, now=WED_OVERLAP + timedelta(minutes=20))
check(go, "جهت مخالف (SELL) کلید جدا دارد → ارسال می‌شود")

# ورودی خراب در state نباید برنامه را بیندازد
go, _ = should_send_signal({"EURUSD|BUY": {"ts": "not-a-date"}}, sig, JCFG, now=WED_OVERLAP)
check(go, "state خراب → با احتیاط ارسال می‌شود (سقوط نمی‌کند)")
go, _ = should_send_signal({"EURUSD|BUY": "رشتهٔ اشتباه"}, sig, JCFG, now=WED_OVERLAP)
check(go, "ورودی غیرdict هم تحمل می‌شود")

print()
print("=" * 78)
print("۹) ژورنال سیگنال (پایهٔ مرحله ۴)")
print("=" * 78)
rec = sig.to_journal(sent=True)
need = {"kind", "id", "ts", "symbol", "direction", "entry", "sl", "tp", "pip",
        "atr", "risk_pips", "reward_pips", "rr", "score", "max_score",
        "session", "evidences", "sent"}
check(need <= set(rec), f"همهٔ فیلدهای ژورنال حاضرند (کم: {need - set(rec)})")
check(rec["kind"] == "signal" and bool(rec["id"]),
      "رکورد سیگنال kind/id دارد (پایهٔ event-sourcing)")

# ژورنال event-source: نتیجه به‌صورت رکورد جدا با همان id گره می‌خورد
import tempfile
from src.journal.store import Journal, TP
from src.journal.stats import compute_stats
with tempfile.TemporaryDirectory() as td:
    jr = Journal(os.path.join(td, "s.jsonl"))
    jr.append(rec)
    jr.add_outcome(rec["id"], TP, rec["tp"], rec["rr"], note="تست")
    loaded = jr.load()
    check(len(loaded) == 1 and loaded[0].outcome == TP and loaded[0].r == rec["rr"],
          "رکورد outcome با همان id به سیگنال گره خورد")
    check(loaded[0].is_win and not loaded[0].is_open, "سیگنال بسته به‌درستی علامت خورد")
    st = compute_stats(loaded, loaded[0].ts)
    check(st.overall.wins == 1 and st.overall.hit_rate == 1.0,
          f"آمار: ۱ برد و نرخ برد ۱۰۰٪ (wins={st.overall.wins}, hr={st.overall.hit_rate})")
check(all(isinstance(x, str) and ":" in x for x in rec["evidences"]),
      f"مدارک به‌شکل قابل‌پارس ذخیره شدند: {rec['evidences'][:3]}")
import json as _json
check(_json.loads(_json.dumps(rec, ensure_ascii=False))["symbol"] == sig.symbol,
      "رکورد JSON-serializable است")

print()
print("=" * 78)
if FAILS:
    print(f"❌ {len(FAILS)} خطا:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ تست‌های داور امتیازدهی پاس شدند")
