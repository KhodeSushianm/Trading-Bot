#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حالت خط‌فرمان (بدون پنل گرافیکی) — برای تست و توسعه.

استفاده:
    python main.py                     # یک چرخهٔ کامل: تکنیکال + تقویم + اخبار + گزارش
    python main.py --briefing          # فقط بریفینگ صبحگاهی 🌅
    python main.py --alerts            # فقط بررسی/ارسال هشدار رویدادهای پراثر 🚨
    python main.py --no-fundamental    # بدون تقویم و اخبار (فقط تکنیکال)
    python main.py --source yahoo      # فقط Yahoo
    python main.py --selftest          # خودآزمون بدون اینترنت (برای CI)
    python main.py --config my.yaml

برای استفادهٔ روزمره، پنل گرافیکی را اجرا کنید:  python panel.py  (یا EXE)
"""
from __future__ import annotations

import argparse
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

    print(f"SELFTEST OK — {len(evs)} رویداد پارس شد، {len(cases)} حالت جهت‌دهی درست، "
          f"۱ هشدار رویداد در پنجرهٔ درست، کدگذاری کنسول سالم، گزارش‌ها {len(rep)} کاراکتر")
    return 0


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

    if args.briefing:
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
        res = run_cycle(cfg, on_log=log)

    if res["report"]:
        print(res["report"])
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
