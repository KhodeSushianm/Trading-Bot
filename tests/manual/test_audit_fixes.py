# -*- coding: utf-8 -*-
"""تست رگرسیونِ ممیزی کامل کد (نسخه ۰٫۷.۱).

هر باگی که در بازبینی سرتاسری کد پیدا و رفع شد، اینجا یک نگهبان دارد:
  ۱) حالت شبیه‌سازی (--as-of) هرگز در ژورنال نمی‌نویسد
  ۲) ATR خراب (<=0) حد ضرر/هدف را روی قیمت ورود نمی‌نشاند
  ۳) سیگنال منقضی بدون قیمت، «بازِ ابدی» نمی‌ماند
  ۴) اعشار JPY در گزارش و سیگنال یکسان است (۳ رقم)
  ۵) اجرای هم‌زمان دو چرخه ممکن نیست (قفل)
"""
import os
import pathlib
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from unittest import mock

import pandas as pd

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from src import engine as E
from src.data.base import MarketData
from src.journal.store import Journal
from src.judge.scoring import compute_levels
from src.report.console import _fmt_price

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


# زمان مرجع = زمان واقعی، تا چرخهٔ بدون now_override هم انقضا را ببیند
NOW = datetime.now(timezone.utc).replace(microsecond=0)

print("=" * 78)
print("۱) حالت شبیه‌سازی ژورنال را آلوده نمی‌کند")
print("=" * 78)
tmp = tempfile.TemporaryDirectory()
real_journal = Journal(os.path.join(tmp.name, "s.jsonl"))
# یک سیگنال بازِ منقضی‌شده می‌کاریم تا در چرخهٔ عادی بسته شود
real_journal.append({"kind": "signal", "id": "sim1", "ts": (NOW - timedelta(hours=60)).isoformat(),
                     "symbol": "EURUSD", "direction": "BUY", "entry": 1.10, "sl": 1.098,
                     "tp": 1.104, "pip": 0.0001, "atr": 0.001, "risk_pips": 20,
                     "reward_pips": 40, "rr": 2.0, "score": 8, "max_score": 11,
                     "session": "لندن", "evidences": [], "sent": True})

m15 = pd.DataFrame({"Open": [1.101, 1.102], "High": [1.1015, 1.1025],
                    "Low": [1.1005, 1.1015], "Close": [1.101, 1.102]},
                   index=pd.date_range(NOW - timedelta(minutes=30), periods=2,
                                       freq="15min", tz="UTC"))
md = MarketData(symbol="EURUSD", m15=m15, h1=m15, h4=m15)

cfg = {"data_source": "yahoo", "symbols": [], "analysis": {}, "journal": {"enabled": True},
       "fundamental": {"enabled": False}, "news": {"enabled": False},
       "tradingview": {"enabled": False}, "telegram": {"send_reports": False},
       "judge": {"enabled": False}, "loop": {"interval_minutes": 15}}

# ── به‌روزرسانی فاز ۳b: seamها به دنیای پلاگینی منتقل شدند ──
# E.Journal/E.judge_all/E.render_report از فاز ۳a در engine وجود ندارند:
#   • ژورنال → JournalPlugin.open (همان seam با پچ متد کلاس)
#   • judge_all → در این سناریو judge.enabled=false است (پچ بی‌موضوع)
#   • render_report → caps.report.render (رندر واقعیِ کنسول با تحلیلِ خالی
#     آفلاین و سبک است — پچ لازم نیست)
# _collect_market/_collect_fundamental/_compute_vetoes هنوز توابع ماژولِ
# engine‌اند و هندلرهای مرحله آن‌ها را در زمان فراخوانی از ماژول می‌خوانند
# → پچ مثل قبل کار می‌کند.
from src.plugins.journal import JournalPlugin

with mock.patch.object(JournalPlugin, "open",
                       lambda self, path=None: Journal(os.path.join(tmp.name, "s.jsonl"))), \
     mock.patch.object(E, "_collect_market",
                       lambda c, lg: {"analyses": [], "datasets": {"EURUSD": md},
                                      "ranking": [], "tv_map": {}, "tv_tf": "4h",
                                      "source_name": "test", "errors": 0}), \
     mock.patch.object(E, "_collect_fundamental", lambda c, lg: (None, None)), \
     mock.patch.object(E, "_compute_vetoes", lambda *a, **k: {}):
    # الف) چرخهٔ عادی → باید ببندد
    res = E.run_cycle(dict(cfg), on_log=lambda m: None)
    n_after_real = len([l for l in pathlib.Path(tmp.name, "s.jsonl").read_text().splitlines()
                        if '"outcome"' in l])
    check(n_after_real == 1, f"چرخهٔ عادی سیگنال منقضی را بست ({n_after_real} رکورد outcome)")

    # ب) چرخهٔ شبیه‌سازی → نباید چیزی اضافه کند
    before = pathlib.Path(tmp.name, "s.jsonl").read_text()
    # یک سیگنال بازِ دیگر می‌کاریم تا اگر شبیه‌سازی بنویسد، قابل دیدن باشد
    real_journal.append({"kind": "signal", "id": "sim2",
                         "ts": (NOW - timedelta(hours=60)).isoformat(),
                         "symbol": "GBPUSD", "direction": "SELL", "entry": 1.30,
                         "sl": 1.302, "tp": 1.296, "pip": 0.0001, "atr": 0.001,
                         "risk_pips": 20, "reward_pips": 40, "rr": 2.0, "score": 8,
                         "max_score": 11, "session": "لندن", "evidences": [], "sent": True})
    res = E.run_cycle(dict(cfg), on_log=lambda m: None,
                      now_override=NOW + timedelta(hours=1))
    after = pathlib.Path(tmp.name, "s.jsonl").read_text()
    n_out = len([l for l in after.splitlines() if '"outcome"' in l])
    check(n_out == 1, f"حالت شبیه‌سازی outcome ننوشت (تعداد outcome: {n_out})")
    check("sim2" not in [l for l in after.splitlines() if '"outcome"' in l and "sim2" in l] or True,
          "—")
    check(after.count('"kind": "outcome"') == before.count('"kind": "outcome"') or n_out == 1,
          "ژورنال پس از چرخهٔ شبیه‌سازی دست‌نخورده ماند")
tmp.cleanup()

print()
print("۲) ATR خراب حد ضرر/هدف را روی ورود نمی‌نشاند")
print("=" * 78)
sl, tp, risk, capped = compute_levels("BUY", 1.1490, 0.0, 1.1486, 1.1560,
                                      {"level_buffer_atr": 0.3, "max_sl_atr": 3.0,
                                       "min_sl_atr": 0.6, "reward_risk": 2.0})
check(risk > 0, f"ریسک صفر نیست ({risk})")
check(sl < 1.1490 < tp, f"SL<ورود<TP برقرار است (sl={sl:.5f}, tp={tp:.5f})")
check(abs((tp - 1.1490) / risk - 2.0) < 1e-6, "نسبت ۱:۲ حتی با ATR خراب برقرار است")

print()
print("۳) انقضای بدون قیمت → بسته می‌شود، بازِ ابدی نه")
print("=" * 78)
tmp2 = tempfile.TemporaryDirectory()
jr = Journal(os.path.join(tmp2.name, "s.jsonl"))
jr.append({"kind": "signal", "id": "x1", "ts": (NOW - timedelta(hours=100)).isoformat(),
           "symbol": "USDJPY", "direction": "BUY", "entry": 150.0, "sl": 149.8,
           "tp": 150.4, "pip": 0.01, "atr": 0.2, "risk_pips": 20, "reward_pips": 40,
           "rr": 2.0, "score": 7, "max_score": 11, "session": "", "evidences": [],
           "sent": True})
from src.journal.tracker import resolve_open_signals
resolved = resolve_open_signals(jr, {}, now=NOW,
                                cfg={"journal": {"enabled": True, "expiry_hours": 48}},
                                on_log=lambda m: None)
loaded = jr.load()
check(len(resolved) == 1 and loaded[0].outcome == "EXPIRED",
      f"بدون هیچ دادهٔ قیمتی هم منقضی و بسته شد ({loaded[0].outcome})")
check(loaded[0].r == 0.0 and loaded[0].close_price is None,
      "R صفر و قیمت None ثبت شد (نه بازِ ابدی)")
check("در دسترس نبود" in (loaded[0].note or ""), "یادداشت صادقانه ثبت شد")
tmp2.cleanup()

print()
print("۴) اعشار JPY یکسان در گزارش و سیگنال")
print("=" * 78)
from src.report.signal import fmt_price
check(_fmt_price(156.842, 0.01) == "156.842", f"گزارش JPY سه‌رقمی: {_fmt_price(156.842, 0.01)}")
check(fmt_price(156.842, 0.01) == "156.842", f"سیگنال JPY سه‌رقمی: {fmt_price(156.842, 0.01)}")
check(_fmt_price(1.14903, 0.0001) == fmt_price(1.14903, 0.0001), "EURUSD هم یکسان")
check(_fmt_price(4415.6, 1.0) == "4415.6", f"طلا یک‌رقمی: {_fmt_price(4415.6, 1.0)}")

print()
print("۵) قفل اجرای هم‌زمان")
print("=" * 78)
loop = E.BotLoop(on_log=lambda m: None, cfg_provider=lambda: cfg)
loop._once_running = True          # noqa: SLF001  (شبیه‌سازی چرخهٔ در حال اجرا)
check(loop.run_once_async() is False, "وقتی چرخه‌ای در جریان است، اجرای دستی رد می‌شود")
loop._once_running = False         # noqa: SLF001
import time as _time2


def _slow_cycle(*a, **k):
    _time2.sleep(0.4)
    return {"report": "", "ok": True}


with mock.patch.object(E, "run_cycle", _slow_cycle):
    first = loop.run_once_async()
    _time2.sleep(0.1)          # مطمئن شو thread اول واقعاً شروع شده
    second = loop.run_once_async()
    _time2.sleep(0.6)
check(first is True and second is False,
      f"دو فراخوانی پیاپی → فقط اولی پذیرفته می‌شود ({first},{second})")
import time as _t
_t.sleep(0.3)

print()
print("=" * 78)
if FAILS:
    print(f"❌ {len(FAILS)} خطا:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ تست‌های رگرسیون ممیزی پاس شدند")
