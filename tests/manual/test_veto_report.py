# -*- coding: utf-8 -*-
"""تست نمایش وتو داخل گزارش کامل + تست هشدار رویداد."""
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
from datetime import datetime, timedelta, timezone


from src.analysis.technical import SymbolAnalysis
from src.fundamental import calendar as cal
from src.report.console import render_report

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


now = datetime(2026, 9, 21, 17, 50, tzinfo=timezone.utc)
raw = [
    {"country": "USD", "date": "2026-09-21T14:00:00-04:00", "title": "Federal Funds Rate",
     "impact": "High", "forecast": "4.00%", "previous": "3.75%"},          # 18:00 UTC → ۱۰ دقیقه دیگر
    {"country": "EUR", "date": "2026-09-22T09:00:00+02:00", "title": "CPI y/y",
     "impact": "High", "forecast": "2.1%", "previous": "2.0%"},            # فردا
]
snap = cal.CalendarSnapshot(events=cal.parse_events(raw), fetched=True, week_range=("2026-09-20", "2026-09-26"))
syms = [{"name": "EURUSD", "base": "EUR", "quote": "USD", "pip": 0.0001, "fa": "یورو به دلار"},
        {"name": "XAUUSD", "base": "XAU", "quote": "USD", "pip": 1.0, "fa": "طلا"}]


def mk(symbol, base, quote, verdict, price):
    return SymbolAnalysis(symbol=symbol, fa_name=symbol, base=base, quote=quote, price=price,
                          pip=0.0001 if base != "XAU" else 1.0, trend="bearish", h1_agrees=True,
                          adx=32.0, rsi=61.0, rsi_rising=False, atr=0.0009,
                          support=price - 0.004, resistance=price + 0.004,
                          last_candle=now, verdict=verdict)


analyses = [mk("EURUSD", "EUR", "USD", "SELL_SETUP", 1.1490), mk("XAUUSD", "XAU", "USD", "WAIT", 4415.6)]
vetoes = {"EURUSD": cal.veto_for_symbol(snap, "EUR", "USD", now, minutes=30)}
check(bool(vetoes["EURUSD"]), f"وتو برای EURUSD فعال شد: {[e.title for e in vetoes['EURUSD']]}")
check(not cal.veto_for_symbol(snap, "GBP", "JPY", now, 30), "GBPJPY نباید وتو شود")

rep = render_report(analyses, [], "yahoo", cal_snap=snap, news_snap=None,
                    symbols_cfg=syms, vetoes=vetoes, cal_horizon=48, now=now)
print()
print("─" * 70)
print(rep)
print("─" * 70)
print()
check("🚫 وتو فعال" in rep, "خط وتو داخل گزارش چاپ شد")
check("وتوی خبری فعال" in rep, "جمع‌بندی نماد وتوشده عوض شد")
check("نرخ بهره فدرال رزرو" in rep, "عنوان فارسی رویداد در گزارش است")
check("۱۰ دقیقه دیگر" in rep, f"شمارش معکوس فارسی درست است")
check("🏦 تقویم اقتصادی" in rep, "بخش تقویم در گزارش است")
check("تورم سالانه" in rep, "عنوان‌ها به فارسی ترجمه شده‌اند")
check("رویداد پراثر یا متوسطی در این بازه نیست" not in rep,
      "بخش تقویم هم همان now را می‌بیند و رویدادِ نزدیک را فهرست می‌کند")

# نمادِ وتونشده باید جمع‌بندی عادی داشته باشد
xau_block = rep.split("📊 XAUUSD")[1].split("───")[0]
check("وتو فعال" not in xau_block, "XAUUSD (که وتو نشده) جمع‌بندی عادی دارد")

print()
print("۲) تست --alerts --dry-run")
import subprocess
r = subprocess.run([sys.executable, "main.py", "--alerts", "--dry-run"],
                   capture_output=True, text=True, cwd=str(_ROOT), timeout=180)
out = (r.stdout + r.stderr)
print("   exit:", r.returncode)
for line in out.splitlines()[-8:]:
    print("   |", line[:110])
check(r.returncode == 0, "--alerts بدون خطا اجرا شد")
check("هشدار" in out or "رویداد پراثری" in out, "خروجی معنادار دارد")

print()
print("=" * 70)
if FAILS:
    print(f"❌ {len(FAILS)} خطا: {FAILS}")
    sys.exit(1)
print("✅ همهٔ تست‌های وتو و هشدار پاس شدند")
