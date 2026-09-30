#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حالت خط‌فرمان (بدون پنل گرافیکی) — برای تست و توسعه.

استفاده:
    python main.py                     # یک چرخهٔ کامل: تکنیکال + تقویم + اخبار + گزارش
    python main.py --briefing          # فقط بریفینگ صبحگاهی 🌅
    python main.py --alerts            # فقط بررسی/ارسال هشدار رویدادهای پراثر 🚨
    python main.py --signals           # فقط سیگنال‌های صادرشده را چاپ کن 🎯
    python main.py --journal           # 📊 کارنامهٔ دقت (کلی + هفتگی + تفکیک‌ها)
    python main.py --nightly           # 🌙 خلاصهٔ شبانه
    python main.py --as-of "2026-09-23 14:00"   # ⚠️ شبیه‌سازی: داور را در یک
                                                #    زمان فرضی بسنج (بازار بسته/تعطیل)
    python main.py --no-fundamental    # بدون تقویم و اخبار (فقط تکنیکال)
    python main.py --source yahoo      # فقط Yahoo
    python main.py --selftest          # خودآزمون بدون اینترنت (برای CI)
    python main.py --config my.yaml

برای استفادهٔ روزمره، پنل گرافیکی را اجرا کنید:  python panel.py  (یا EXE)
"""
from __future__ import annotations

import argparse
import os
import sys

from src import app_paths
from src.config import load_config
from src.engine import check_event_alerts, run_briefing, run_cycle


def _fix_windows_console() -> None:
    """اطمینان از اینکه کنسول متن فارسی و ایموجی را درست نمایش دهد.

    پیاده‌سازی مشترک با پنل در src/app_paths.fix_console_encoding —
    آن نسخه علاوه بر reconfigure، جریان‌های بدون buffer را هم پوشش می‌دهد.
    """
    app_paths.fix_console_encoding()


def _selftest() -> int:
    """خودآزمون بدون اینترنت — منطق فاندامنتال/اخبار را با دادهٔ ثابت می‌سنجد."""
    from datetime import datetime, timedelta, timezone

    from src.fundamental import calendar as cal
    from src.fundamental import news as nw
    from src.report.fundamental import render_calendar, render_news

    # ۱) تقویم: پارس کردن JSON خام
    raw = [
        {"country": "USD", "date": "2026-09-16T14:00:00-04:00", "title": "Federal Funds Rate",
         "impact": "High", "forecast": "4.00%", "previous": "3.75%"},
        {"country": "EUR", "date": "2026-09-16T09:00:00+02:00", "title": "CPI y/y",
         "impact": "High", "forecast": "2.1%", "previous": "2.0%"},
        {"country": "GBP", "date": "2026-09-17T06:00:00+01:00", "title": "Claimant Count Change",
         "impact": "High", "forecast": "8.3K", "previous": "-11.0K"},
    ]
    evs = cal.parse_events(raw)
    assert len(evs) == 3, f"انتظار ۳ رویداد، {len(evs)} شد"
    assert all(e.when.tzinfo is not None for e in evs), "همه زمان‌ها باید UTC-aware باشند"
    assert [e.when for e in evs] == sorted(e.when for e in evs), "رویدادها باید زمانی مرتب شوند"
    by_title = {e.title: e for e in evs}

    eur_cpi = by_title["CPI y/y"]
    fed = by_title["Federal Funds Rate"]
    claimant = by_title["Claimant Count Change"]
    assert eur_cpi.when.hour == 7, f"تبدیل منطقهٔ زمانی اشتباه: {eur_cpi.when}"   # 09:00+02 → 07:00Z
    assert eur_cpi.title_fa == "تورم سالانه (CPI)", eur_cpi.title_fa
    assert eur_cpi.category == "تورم و قیمت‌ها", eur_cpi.category
    assert fed.category == "نرخ بهره و بانک مرکزی", fed.category
    assert claimant.category == "اشتغال و بازار کار", claimant.category
    assert eur_cpi.polarity == 1 and fed.polarity == 1, "CPI و نرخ بهره: بالاتر = تقویت ارز"
    assert claimant.polarity == -1, "شمار بیکاران: کمتر = تقویت ارز"
    assert eur_cpi.affects("EUR", "USD") and not eur_cpi.affects("GBP", "JPY")

    # ۲) وتو: رویداد پراثر نزدیک باید سیگنال را ممنوع کند
    snap = cal.CalendarSnapshot(events=evs, source="selftest")
    t = fed.when                                                 # 18:00 UTC نرخ بهره آمریکا
    assert cal.veto_for_symbol(snap, "EUR", "USD", t - timedelta(minutes=10), 30), "وتو باید فعال شود"
    assert cal.veto_for_symbol(snap, "EUR", "USD", t + timedelta(minutes=5), 30), \
        "۵ دقیقه بعد از رویداد هم وتو است"
    assert not cal.veto_for_symbol(snap, "EUR", "USD", t + timedelta(hours=3), 30), \
        "بعد از ۳ ساعت وتو برداشته می‌شود"
    assert not cal.veto_for_symbol(snap, "AUD", "NZD", t, 30), "رویداد USD نباید AUDNZD را وتو کند"
    assert cal.next_high_impact(snap, "USD", "JPY", now=t - timedelta(hours=1)) is fed

    # ۳) اخبار: جهت‌دهی
    cases = {
        "Japanese Yen slides as markets look beyond BoJ rate hike": {"JPY": -1},
        "USDJPY surges as the BOJ hike disappoints": {"USD": 1, "JPY": -1},
        "Sterling rises against the dollar as UK CPI beats expectations": {"GBP": 1, "USD": -1},
        "Gold rallies as war fears drive safe-haven demand": {"XAU": 1},
        "investingLive Americas market news wrap: bonds slump": {},
        # سوژهٔ جمله داراییِ خارج از پوشش است → جهت به ارزها نسبت داده نمی‌شود
        "Silver soars by more than 7% as the Fed's dot plot shows low appetite for hikes": {},
        "Bitcoin plunges as risk appetite collapses": {},
        # سوژه داراییِ پوشش‌داده‌شده → فقط همان دارایی جهت می‌گیرد، نه ارزِ اشارهٔ جانبی
        "Gold slides after China data disappoints": {"XAU": -1},
        # مداخلهٔ ارزی ژاپن همیشه به نفع ین است
        "Japan conducted an FX rate check earlier": {"JPY": 1},
    }
    for text, want in cases.items():
        _score, got, _kw, _brk, _rnd = nw.score_text(text)
        assert got == want, f"جهت اشتباه برای «{text[:45]}...»: {got} ≠ {want}"

    # ۳ب) خبرهای با «امضای جهت» یکسان باید یک بار شمرده شوند (نه سه بار)
    dup = nw.NewsSnapshot(items=[
        nw.NewsItem(title="Gold extends gains", score=5, direction={"XAU": 1, "USD": -1}, source="a"),
        nw.NewsItem(title="Gold appreciates further", score=5, direction={"XAU": 1, "USD": -1}, source="b"),
        nw.NewsItem(title="Bullion rallies", score=5, direction={"XAU": 1, "USD": -1}, source="c"),
    ])
    v = nw.news_supports(dup, "XAU", "USD", "buy")
    assert len(v.support) == 1, f"روایت تکراری سه بار شمرده شد: {len(v.support)}"
    assert v.verdict == 1 and v.votes == 1.0, (v.votes, v.verdict)

    # ۴) گزارش‌نویسی نباید بشکند
    now = datetime(2026, 9, 16, 17, 30, tzinfo=timezone.utc)
    syms = [{"name": "EURUSD", "base": "EUR", "quote": "USD"},
            {"name": "USDJPY", "base": "USD", "quote": "JPY"}]
    rep = render_calendar(snap, syms, now=now, horizon_hours=48)
    assert "تقویم اقتصادی" in rep and len(rep) > 100
    empty = cal.CalendarSnapshot(events=[], source="selftest")
    assert "تقویم خالی" in render_calendar(empty, syms, now=now)
    broken = cal.CalendarSnapshot(error="timeout")
    assert "در دسترس نبود" in render_calendar(broken, syms, now=now)
    # حالت آخر هفته: رویدادها هستند ولی هیچ‌کدام در بازهٔ پیش‌رو نیستند
    past_only = cal.CalendarSnapshot(events=evs, fetched=True, source="selftest",
                                     week_range=("2026-09-13", "2026-09-19"))
    txt_weekend = render_calendar(past_only, syms,
                                  now=datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc),
                                  horizon_hours=48)
    assert "پنجرهٔ معاملاتی باز است" in txt_weekend, txt_weekend[:200]
    assert "فید ForexFactory فقط هفتهٔ جاری" in txt_weekend

    ns = nw.NewsSnapshot(items=[nw.NewsItem(title="Dollar rallies on hawkish Fed",
                                            score=5, direction={"USD": 1}, source="test")],
                         feeds_ok=1)
    assert "اخبار بازار" in render_news(ns)
    assert "در دسترس" in render_news(nw.NewsSnapshot(error="feed down"))

    # ۵) هشدار رویداد: فقط داخل پنجرهٔ زمانی و فقط برای ارزهای تحت پوشش
    from src.engine import check_event_alerts
    acfg = {"symbols": syms,
            "fundamental": {"enabled": True, "alerts_enabled": True,
                            "alert_before_minutes": 30, "alert_grace_minutes": 10}}
    fired = check_event_alerts(acfg, cal_snap=snap, on_log=lambda _m: None,
                               now=fed.when - timedelta(minutes=12), dry_run=True)
    assert len(fired) == 1, f"باید دقیقاً ۱ هشدار باشد، {len(fired)} شد"
    assert fired[0]["event"].title == "Federal Funds Rate", fired[0]["event"].title
    assert "هشدار رویداد پراثر" in fired[0]["text"]
    assert "USDJPY" in fired[0]["text"] and "EURUSD" in fired[0]["text"], "جفت‌های متاثر باید ذکر شوند"
    # خارج از پنجره → هیچ هشداری
    assert check_event_alerts(acfg, cal_snap=snap, now=fed.when + timedelta(hours=2),
                              dry_run=True) == [], "هشدار باید فقط در پنجرهٔ زمانی باشد"
    # رویدادِ ارزِ خارج از پوشش ما (CNY) نباید هشدار بدهد
    cny = cal.parse_events([{"country": "CNY", "date": "2026-09-16T10:00:00+08:00",
                             "title": "M2 Money Supply y/y", "impact": "High",
                             "forecast": "8.8%", "previous": "8.8%"}])
    assert check_event_alerts(acfg, cal_snap=cal.CalendarSnapshot(events=cny),
                              now=cny[0].when, dry_run=True) == [], "CNY در پوشش ما نیست"

    # ۶) کدگذاری کنسول — باگ واقعی نسخهٔ ۰٫۲: print فارسی روی کنسول cp1252
    #    ویندوز UnicodeEncodeError می‌داد و چون داخل try/except موتور بود،
    #    بی‌صدا کل لایهٔ داده از کار می‌افتاد.
    import io

    from src import app_paths
    buf = io.BytesIO()
    fake = io.TextIOWrapper(buf, encoding="cp1252", errors="strict")   # مثل کنسول ویندوز
    real_out = sys.stdout
    sys.stdout = fake
    try:
        app_paths.fix_console_encoding()
        print("فارسی ✅ وتو 🚫 تقویم 🏦")            # نباید استثنا بدهد
        fake.flush()                                  # TextIOWrapper بافر دارد
    finally:
        sys.stdout = real_out
    got = buf.getvalue().decode("utf-8", "replace")
    assert "فارسی" in got and "🚫" in got, f"خروجی باید UTF-8 باشد، شد: {got!r}"

    # ۷) ⚖️ داور امتیازدهی (مرحله ۳) — مسیر سیگنال، وتوها و ریاضی حد ضرر
    from src.analysis.technical import SymbolAnalysis
    from src.data.tradingview import TVSnapshot
    from src.fundamental.news import NewsItem, NewsSnapshot
    from src.judge.scoring import JudgeContext, compute_levels, judge_symbol
    from src.judge.session import market_status
    from src.report.signal import render_judge_summary, render_signal

    jcfg = judge_cfg_default()
    wed = datetime(2026, 9, 23, 14, 0, tzinfo=timezone.utc)     # چهارشنبه، هم‌پوشانی لندن/NY
    sat = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)     # شنبه، بازار بسته
    # v0.29.1: هم‌عدد با config.yaml (adx_min_trend 30 · adx_strong 40).
    # نمونهٔ زیر adx=32 دارد → با adx_strong=40 یک امتیاز می‌گیرد نه دو تا،
    # پس امتیاز از ۱۱ به ۱۰ می‌رسد و همچنان بالای آستانهٔ ۷ است.
    acfg = {"ema_fast": 50, "ema_slow": 200, "adx_period": 14, "adx_min_trend": 30,
            "adx_strong": 40, "rsi_period": 14, "atr_period": 14, "swing_window": 5}

    def _ana(**kw):
        d = dict(symbol="EURUSD", fa_name="یورو به دلار", base="EUR", quote="USD",
                 price=1.1490, pip=0.0001, trend="bullish", h1_agrees=True, adx=32.0,
                 rsi=38.0, rsi_rising=True, atr=0.0010, support=1.1486, resistance=1.1560,
                 last_candle=wed, verdict="BUY_SETUP")
        d.update(kw)
        return SymbolAnalysis(**d)

    def _ctx(now=wed, cal=None, news=None, **over):
        c = dict(jcfg)
        c.update(over)
        return JudgeContext(jcfg=c, acfg=acfg, symbols_cfg=syms,
                            ranking=[("EUR", 0.3), ("GBP", 0.1), ("USD", -0.2), ("JPY", -0.4)],
                            tv_map={"EURUSD": TVSnapshot("EURUSD", 1.149, 41.0, 32.0,
                                                         "BUY", 13, 4, 9)},
                            cal_snap=cal, news_snap=news, now=now,
                            status=market_status(now), event_veto_minutes=30.0)

    clean = cal.CalendarSnapshot(events=cal.parse_events([
        {"country": "USD", "date": "2026-09-28T14:00:00-04:00", "title": "CPI y/y",
         "impact": "High", "forecast": "2.1%", "previous": "2.0%"}]), fetched=True)
    supportive = NewsSnapshot(items=[NewsItem(
        title="Euro rallies as ECB turns hawkish", score=5,
        direction={"EUR": 1, "USD": -1}, source="test", published=wed)], feeds_ok=1)

    # الف) مسیر طلایی → سیگنال با همهٔ مدارک
    jg = judge_symbol(_ana(), {}, None, _ctx(cal=clean, news=supportive))
    assert jg.signal is not None, f"باید سیگنال بدهد، reject={jg.reject_reason} vetoes={[v.key for v in jg.vetoes]}"
    sg = jg.signal
    assert sg.max_score == 11, f"حداکثر امتیاز باید ۱۱ باشد، {sg.max_score} شد"
    assert sg.score >= int(jcfg["min_score"]), f"امتیاز {sg.score} زیر آستانه است"
    assert sg.sl < sg.entry < sg.tp, "در سیگنال خرید: SL < ورود < TP"
    assert abs(sg.reward_pips - sg.rr * sg.risk_pips) < 0.6, "هدف باید rr برابر ریسک باشد"
    assert 1 <= sg.stars <= 5, f"ستاره‌ها {sg.stars}"

    msg = render_signal(sg)
    for needle in ("سیگنال خرید", "پشتوانه:", "📍 ورود", "🛑 حد ضرر", "🎯 هدف",
                   "ریسک پیشنهادی", "نه دستور معامله"):
        assert needle in msg, f"«{needle}» در پیام سیگنال نیست"
    assert "= ۷ پیپ" not in msg and msg.count("پیپ فاصله") == 2, \
        "فاصلهٔ حد ضرر/هدف باید یک‌بار و بدون تکرار چاپ شود"

    # ب) هر وتو باید جداگانه سیگنال را متوقف کند
    veto_cases = {
        "WEEKEND": (_ctx(now=sat, cal=clean, news=supportive), _ana()),
        "TF_CONFLICT": (_ctx(cal=clean, news=supportive), _ana(h1_agrees=False)),
        "RANGE": (_ctx(cal=clean, news=supportive), _ana(adx=14.0)),
        "DATA": (_ctx(cal=clean, news=supportive), _ana(verdict="DATA")),
        "EVENT": (_ctx(cal=cal.CalendarSnapshot(events=[cal.CalendarEvent(
            when=wed + timedelta(minutes=12), country="USD", title="Federal Funds Rate",
            title_fa="نرخ بهره", impact="HIGH", forecast="4.00%", previous="3.75%")],
            fetched=True), news=supportive), _ana()),
        "BREAKING_NEWS": (_ctx(cal=clean, news=NewsSnapshot(items=[NewsItem(
            title="BREAKING: ECB surprise", score=6, direction={"EUR": -1},
            breaking=True, source="t", published=wed)], feeds_ok=1)), _ana()),
    }
    for key, (c, aa) in veto_cases.items():
        r = judge_symbol(aa, {}, None, c)
        assert r.signal is None, f"وتوی {key} جلوی سیگنال را نگرفت"
        assert r.reject_reason == "VETO", f"reject_reason برای {key} = {r.reject_reason}"
        assert key in [v.key for v in r.vetoes], f"{key} در فهرست وتوها نیست: {[v.key for v in r.vetoes]}"

    # وتوها باید از config قابل خاموش‌کردن باشند
    r = judge_symbol(_ana(), {}, None, _ctx(now=sat, cal=clean, news=supportive,
                                            veto={**jcfg["veto"], "weekend": False}))
    assert "WEEKEND" not in [v.key for v in r.vetoes], "وتو باید تنظیم‌پذیر باشد"

    # پ) امتیاز ناکافی → رد با دلیل روشن، بدون بادکردن امتیاز
    weak = JudgeContext(jcfg=jcfg, acfg=acfg, symbols_cfg=syms,
                        ranking=[("USD", 0.4), ("JPY", 0.2), ("GBP", 0.0), ("EUR", -0.3)],
                        tv_map={"EURUSD": TVSnapshot("EURUSD", 1.149, 62.0, 32.0, "SELL", 3, 14, 9)},
                        cal_snap=cal.CalendarSnapshot(error="timeout"),
                        news_snap=NewsSnapshot(error="down"),
                        now=datetime(2026, 9, 23, 3, 0, tzinfo=timezone.utc),
                        status=market_status(datetime(2026, 9, 23, 3, 0, tzinfo=timezone.utc)),
                        event_veto_minutes=30.0)
    r = judge_symbol(_ana(), {}, None, weak)
    assert r.signal is None and r.reject_reason == "LOW_SCORE", f"reject={r.reject_reason}"
    assert r.score < int(jcfg["min_score"]), f"امتیاز {r.score} باید زیر آستانه باشد"
    for e in r.evidences:
        if e.key in ("fundamental", "news", "tv", "session", "strength"):
            assert e.points == 0, f"مدرک {e.key} با دادهٔ نامناسب {e.points} امتیاز گرفت"
    assert any(e.unavailable for e in r.evidences), \
        "مدرکِ بدون داده باید unavailable علامت بخورد، نه اینکه صفرِ بی‌دلیل بگیرد"

    # ت) ستاپ نبودن → دلیل انسانی
    r = judge_symbol(_ana(verdict="WAIT"), {}, None, _ctx(cal=clean, news=supportive))
    assert r.signal is None and r.reject_reason == "NO_SETUP", f"reject={r.reject_reason}"
    assert r.reject_detail, "رد شدن باید دلیل داشته باشد"

    # ث) ریاضی حد ضرر
    rc = jcfg["risk"]
    sl, tp, risk, capped = compute_levels("BUY", 1.1490, 0.0010, 1.1486, 1.1560, rc)
    assert sl < 1.1486 and tp > 1.1490 and not capped, "SL زیر حمایت، TP بالای ورود"
    assert abs((tp - 1.1490) / (1.1490 - sl) - float(rc["reward_risk"])) < 1e-6, "نسبت R:R دقیق"
    sl2, tp2, _, _ = compute_levels("SELL", 1.1490, 0.0010, 1.1440, 1.1495, rc)
    assert sl2 > 1.1495 and tp2 < 1.1490, "در فروش: SL بالای مقاومت، TP زیر ورود"
    _, _, r3, _ = compute_levels("BUY", 1.1490, 0.0010, None, None, rc)
    assert abs(r3 - float(rc["sl_atr_multiplier"]) * 0.0010) < 1e-9, "بدون سطح: fallback بر پایهٔ ATR"
    _, _, r4, cap4 = compute_levels("BUY", 1.1490, 0.0010, 1.1400, None, rc)
    assert cap4 and abs(r4 - float(rc["max_sl_atr"]) * 0.0010) < 1e-9, "سطح دور → سقف max_sl_atr"
    _, _, r5, _ = compute_levels("BUY", 1.1490, 0.0010, 1.14895, None, rc)
    assert abs(r5 - float(rc["min_sl_atr"]) * 0.0010) < 1e-9, "سطح چسبیده → کف min_sl_atr"

    # ج) سقف تعداد سیگنال + خلاصهٔ داور
    # v0.29.1: ADXها با آستانه‌های تازه (min_trend=30 · strong=40) بازنویسی
    # شدند. پیش‌تر سومی adx=21 داشت تا «نامزدِ ضعیف‌تر» باشد؛ حالا ۲۱ زیرِ
    # کفِ ۳۰ است و veto_range ردش می‌کند — یعنی CAPPED نمی‌شد و شمارشِ
    # «۲ تا CAPPED» می‌شکست. این رفتارِ *درستِ* تازه است، نه باگ.
    # مقادیرِ تازه عمداً سه سطحِ متمایز می‌سازند تا «بهترین نگه داشته می‌شود»
    # معنا داشته باشد (و نه تساویِ سه‌تایی که آزمون را پوچ می‌کرد):
    #   ۴۵ ≥ strong → ۲ امتیازِ ev_trend   ·   ۳۵ و ۳۱ → ۱ امتیاز
    many = [_ana(symbol="EURUSD", adx=45.0),
            _ana(symbol="GBPUSD", base="GBP", quote="USD", adx=35.0),
            _ana(symbol="AUDUSD", base="AUD", quote="USD", adx=31.0)]
    from src.judge.scoring import judge_all
    out = judge_all(many, {}, _ctx(cal=clean, news=supportive, max_signals_per_cycle=1))
    assert sum(1 for o in out if o.signal) == 1, "سقف ۱ سیگنال باید رعایت شود"
    assert sum(1 for o in out if o.reject_reason == "CAPPED") == 2, "بقیه باید CAPPED شوند"
    kept = [o for o in out if o.signal][0]
    assert kept.score == max(o.score for o in out), "بهترین سیگنال باید نگه داشته شود"
    summ = render_judge_summary(out, min_score=int(jcfg["min_score"]), now=wed)
    assert "⚖️ داور امتیازدهی" in summ and "سرنوشت بقیهٔ نمادها" in summ
    nosig = render_judge_summary([judge_symbol(_ana(verdict="WAIT", adx=15.0), {}, None,
                                               _ctx(cal=clean, news=supportive))])
    assert "هیچ سیگنالی صادر نشد" in nosig, "حالت بدون سیگنال باید صادقانه اعلام شود"

    # چ) ژورنال سیگنال (پایهٔ مرحله ۴)
    import json as _json
    rec = sg.to_journal(sent=True)
    need = {"kind", "id", "ts", "symbol", "direction", "entry", "sl", "tp", "pip",
            "atr", "risk_pips", "reward_pips", "rr", "score", "max_score",
            "session", "evidences", "sent"}
    assert need <= set(rec), f"فیلدهای ژورنال ناقص: {need - set(rec)}"
    assert rec["kind"] == "signal" and rec["id"], "رکورد سیگنال باید kind/id داشته باشد"

    # ژورنال event-source: نتیجه به‌صورت رکورد جدا با همان id گره می‌خورد
    import tempfile
    from src.journal.store import Journal
    with tempfile.TemporaryDirectory() as td:
        jr = Journal(os.path.join(td, "s.jsonl"))
        jr.append(rec)
        jr.add_outcome(rec["id"], "TP", rec["tp"], rec["rr"], note="تست")
        loaded = jr.load()
        assert len(loaded) == 1, "replay باید دقیقاً یک سیگنال بدهد"
        assert loaded[0].outcome == "TP" and loaded[0].r == rec["rr"], \
            "رکورد outcome باید به سیگنال گره بخورد"
        assert loaded[0].is_win and not loaded[0].is_open
    assert _json.loads(_json.dumps(rec, ensure_ascii=False))["symbol"] == sg.symbol

    # لایسنس (v0.14.0): طرح HMAC — قطعی، آفلاین، و هم‌بُر با ماژول JS اندروید
    from src import license as lic
    did = lic.get_device_id()
    assert did == lic.get_device_id() and len(did) == 64, "شناسهٔ دستگاه باید قطعی و ۶۴ هگز باشد"
    code = lic.get_device_code(did)
    assert code == lic.format_code(did[:12].upper()) and code.count("-") == 2, \
        f"کد دستگاه بدقالبه: {code}"
    key = lic.generate_license_key(code)
    assert key == lic.generate_license_key(code), "کلید باید قطعی باشد"
    assert lic.validate_license(key)[0], "کلید درست باید اعتبارسنجی شود"
    assert lic.validate_license(key.lower().replace("-", " "))[0], "کلید باید به فاصله/حروف کوچک مقاوم باشد"
    assert not lic.validate_license("AAAA-BBBB-CCCC-DDDD")[0], "کلید غلط باید رد شود"
    assert not lic.validate_license("short")[0], "کلید بدقالبه باید رد شود"
    assert not lic.validate_license(key, "FF00-FF00-FF00")[0], "کلید دستگاه دیگر باید رد شود"
    # بُرِد مشترک با license.js اندروید (همان secret، همان HMAC) — در smoke_license.js هم هست
    assert lic.generate_license_key("AB12-CD34-EF56") == "6F1F-8540-078F-9898", \
        "بُرِد آزمایشی مشترک پایتون/JS تغییر کرده — secret دو طرف باید یکی بماند"

    # کارت تصویری سیگنال (v0.19.0) — spec پایتون == spec جاوااسکریپت (smoke_share.js)
    from src.report.sharecard import build_share_spec as _bss
    from datetime import datetime as _dt2, timezone as _tz2
    _spec = _bss({"symbol": "EURUSD", "fa_name": "یورو به دلار آمریکا", "direction": "BUY",
                  "stars": 5, "score": 10, "max_score": 11, "entry": 1.17, "sl": 1.165,
                  "tp": 1.18, "pip": 0.0001, "is_gold": False, "rr": 2.0,
                  "now": _dt2(2026, 9, 21, 12, 0, 0, tzinfo=_tz2.utc),
                  "session_fa": "لندن/نیویورک"}, version="0.19.0")
    assert (_spec["pair"], _spec["dirLabel"], _spec["entry"], _spec["slDist"],
            _spec["scoreFa"], _spec["timeTeh"], _spec["footerTg"]) == \
        ("EUR/USD", "سیگنال خرید", "1.17000", "۵۰ پیپ", "۱۰ از ۱۱", "۱۵:۳۰ تهران",
         "@Khode_Sushian"), f"spec کارت تصویری از وکتور مشترک خارج شد: {_spec}"

    # هشدارهای قیمت (v0.19.0) — چرخهٔ افزودن/شلیک/حذفِ یک‌بارمصرف
    import tempfile as _tf
    from src import alerts as _al
    _prev = os.environ.get("ODIN_DATA_DIR")
    with _tf.TemporaryDirectory() as _td:
        os.environ["ODIN_DATA_DIR"] = _td
        try:
            ok, _w = _al.add_alert("EURUSD", "above", 9.5, pip=0.0001)
            assert ok, "افزودن هشدار ناموفق"
            _f = _al.check_alerts([{"symbol": "EURUSD", "price": 10.0, "pip": 0.0001}])
            assert len(_f) == 1 and _f[0]["_price"] == 10.0, "هشدار شلیک نشد"
            assert _al.check_alerts([{"symbol": "EURUSD", "price": 10.0}]) == [], \
                "هشدار یک‌بارمصرف باید مصرف شود"
        finally:
            if _prev is None:
                os.environ.pop("ODIN_DATA_DIR", None)
            else:
                os.environ["ODIN_DATA_DIR"] = _prev
    # کلید زمان‌دار (v0.15.0) — انقضا داخل رشتهٔ کلید؛ بُرِد مشترک با js/license.js
    timed = lic.generate_license_key("AB12-CD34-EF56", until="2030-12-31")
    assert timed == "19DB-2DFA-F0E7-0082-301231", f"بُرِد کلید زمان‌دار عوض شده: {timed}"
    assert lic.validate_license(timed, "AB12-CD34-EF56")[0], "کلید زمان‌دار معتبر باید پاس شود"
    assert not lic.validate_license(timed, "AB12-CD34-EF56", now=datetime(2031, 1, 1))[0], \
        "کلید زمان‌دار باید پس از انقضا رد شود"
    assert not lic.validate_license("19DB-2DFA-F0E7-0082", "AB12-CD34-EF56")[0], \
        "حذف پسوند تاریخ نباید کلید زمان‌دار را معتبر کند"

    print(f"SELFTEST OK — {len(evs)} رویداد پارس شد، {len(cases)} حالت جهت‌دهی، "
          f"{len(veto_cases)} وتو، سیگنال {sg.score}/{sg.max_score}، "
          f"ریاضی SL/TP، ژورنال، لایسنس (HMAC) و کدگذاری کنسول سالم")
    return 0


def judge_cfg_default() -> dict:
    """پیش‌فرض‌های داور بدون خواندن config.yaml (تا خودآزمون مستقل بماند)."""
    from src.judge.scoring import judge_config
    return judge_config({})


def main() -> None:
    _fix_windows_console()
    parser = argparse.ArgumentParser(description="دستیار سیگنال فارکس — حالت خط‌فرمان")
    parser.add_argument("--config", default=None, help="مسیر فایل پیکربندی YAML")
    parser.add_argument("--source", default=None, choices=["auto", "yahoo", "twelvedata"],
                        help="تغییر موقت منبع داده (بدون ویرایش config)")
    parser.add_argument("--briefing", action="store_true", help="فقط بریفینگ صبحگاهی 🌅")
    parser.add_argument("--alerts", action="store_true", help="فقط بررسی هشدار رویدادهای پراثر 🚨")
    parser.add_argument("--dry-run", action="store_true",
                        help="با --alerts: هشدارها را فقط چاپ کن، به تلگرام نفرست")
    parser.add_argument("--no-fundamental", action="store_true",
                        help="تقویم اقتصادی و اخبار را موقتاً خاموش کن")
    parser.add_argument("--signals", action="store_true",
                        help="فقط پیام سیگنال‌ها را چاپ کن (بدون گزارش کامل)")
    parser.add_argument("--as-of", default=None, metavar="YYYY-MM-DD HH:MM",
                        help="⚠️ شبیه‌سازی: زمان فرضی (UTC) برای داور/سشن/تقویم. "
                             "در این حالت سیگنالی به تلگرام نمی‌رود.")
    parser.add_argument("--journal", action="store_true",
                        help="📊 کارنامهٔ دقت را چاپ کن (و به تلگرام بفرست)")
    parser.add_argument("--nightly", action="store_true",
                        help="🌙 خلاصهٔ شبانه را چاپ کن (و به تلگرام بفرست)")
    parser.add_argument("--selftest", action="store_true", help="خودآزمون بدون اینترنت")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(_selftest())

    cfg = load_config(args.config)
    if args.source:
        cfg["data_source"] = args.source
    if args.no_fundamental:
        cfg.setdefault("fundamental", {})["enabled"] = False
        cfg.setdefault("news", {})["enabled"] = False

    log = lambda m: print(m, file=sys.stderr)  # noqa: E731

    if args.journal or args.nightly:
        from src.engine import run_journal_report
        res = run_journal_report(cfg, on_log=log,
                                 kind="nightly" if args.nightly else "stats")
    elif args.briefing:
        res = run_briefing(cfg, on_log=log)
    elif args.alerts:
        fired = check_event_alerts(cfg, on_log=log, dry_run=args.dry_run)
        for f in fired:
            print("\n" + "=" * 62)
            print(f["text"])
        if not fired:
            print("✅ رویداد پراثری در پنجرهٔ هشدار نیست (یا قبلاً هشدار داده شده)")
        sys.exit(0)
    else:
        res = run_cycle(cfg, on_log=log, now_override=_parse_as_of(args.as_of))

    if args.signals and not args.briefing:
        sigs = res.get("signals") or []
        if not sigs:
            print("⛔ سیگنالی صادر نشد. برای دیدن دلیل رد شدن هر نماد، "
                  "بخش «⚖️ داور امتیازدهی» در گزارش کامل را بخوان (بدون --signals).")
        for x in sigs:
            print(x["text"])
            if not x.get("sent"):
                print("ℹ️ (این سیگنال به تلگرام ارسال نشد: تکراری یا حالت شبیه‌سازی)")
    elif res["report"]:
        print(res["report"])
    sys.exit(0 if res["ok"] else 1)


def _parse_as_of(txt: str | None):
    """تجزیهٔ «YYYY-MM-DD HH:MM» به datetime UTC؛ در صورت خطا، پیام روشن و خروج."""
    if not txt:
        return None
    from datetime import datetime, timezone
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(txt.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    print(f"❌ زمان «{txt}» قابل خواندن نیست. قالب درست: 2026-09-23 14:00  (UTC)",
          file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
