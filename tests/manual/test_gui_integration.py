# -*- coding: utf-8 -*-
"""تست یکپارچگی: پنل GUI (offscreen) + زمان‌بند بریفینگ + وتو + هشدار."""
import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
import time
from datetime import datetime, timedelta, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import panel as P
from src import engine as E
from src.config import load_config
from src.fundamental import calendar as cal

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


print("=" * 78)
print("۱) زمان‌بند بریفینگ — بدون انتظار واقعی")
print("=" * 78)
app = QApplication.instance() or QApplication(sys.argv[:1])
app.setStyle("Fusion")

cfg = load_config()
loop = E.BotLoop(on_log=lambda m: None, cfg_provider=lambda: cfg)

now = datetime(2026, 9, 21, 5, 0, tzinfo=timezone.utc)          # دوشنبه ۰۵:۰۰
nxt = loop.next_briefing_at({"briefing": {"enabled": True, "times_utc": ["06:30"]}}, now)
check(nxt == datetime(2026, 9, 21, 6, 30, tzinfo=timezone.utc), f"بریفینگ بعدی = {nxt} (باید امروز ۰۶:۳۰ باشد)")

nxt2 = loop.next_briefing_at({"briefing": {"enabled": True, "times_utc": ["06:30"]}},
                             datetime(2026, 9, 21, 7, 0, tzinfo=timezone.utc))
check(nxt2 and nxt2.date().day == 22, f"بعد از گذشتن ساعت امروز → فردا ({nxt2})")

check(loop.next_briefing_at({"briefing": {"enabled": False, "times_utc": ["06:30"]}}, now) is None,
      "briefing.enabled=false → هیچ زمان بعدی")
check(loop.next_briefing_at({"briefing": {"enabled": True, "times_utc": []}}, now) is None,
      "times_utc خالی → هیچ زمان بعدی")
check(loop.next_briefing_at({"briefing": {"enabled": True, "times_utc": ["25:99"]}}, now) is None,
      "ساعت نامعتبر نادیده گرفته می‌شود")
multi = loop.next_briefing_at({"briefing": {"enabled": True, "times_utc": ["06:30", "12:00", "03:00"]}}, now)
check(multi == datetime(2026, 9, 21, 6, 30, tzinfo=timezone.utc), f"چند ساعتی → نزدیک‌ترین ({multi})")

print()
print("۲) _maybe_briefing واقعاً در پنجرهٔ catch-up شلیک می‌شود")
_REAL_RUN_BRIEFING = E.run_briefing      # برای بازگرداندن بعد از تست
calls = {"n": 0}
E.run_briefing = lambda cfg=None, on_log=None, **kw: (calls.__setitem__("n", calls["n"] + 1) or
                                                       {"ok": True, "report": "BRIEFING-TEXT"})
loop2 = E.BotLoop(on_log=lambda m: None, on_briefing=lambda t: calls.setdefault("text", t),
                  cfg_provider=lambda: cfg2)
cfg2 = dict(cfg)
cfg2["briefing"] = {"enabled": True, "times_utc": ["06:30"], "catchup_window_minutes": 90}

import src.engine as eng_mod


class _FixedDT(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 9, 21, 7, 0, tzinfo=timezone.utc)   # یک ساعت بعد از ۰۶:۳۰


_real_dt = eng_mod.datetime
eng_mod.datetime = _FixedDT
try:
    loop2._maybe_briefing(cfg2)
    check(calls["n"] == 1, f"بریفینگ دقیقاً یک بار شلیک شد (n={calls['n']})")
    check(calls.get("text") == "BRIEFING-TEXT", "متن بریفینگ به callback رسید")
    loop2._maybe_briefing(cfg2)
    check(calls["n"] == 1, f"بار دوم شلیک نشد (جلوگیری از تکرار روزانه) — n={calls['n']}")
finally:
    eng_mod.datetime = _real_dt

# خارج از پنجرهٔ catch-up (۳ ساعت دیر) → نباید بفرستد
calls2 = {"n": 0}
E.run_briefing = lambda cfg=None, on_log=None, **kw: (calls2.__setitem__("n", calls2["n"] + 1) or
                                                      {"ok": True, "report": "X"})


class _LateDT(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)   # ۳.۵ ساعت بعد


loop3 = E.BotLoop(on_log=lambda m: None, cfg_provider=lambda: cfg2)
eng_mod.datetime = _LateDT
try:
    loop3._maybe_briefing(cfg2)
    check(calls2["n"] == 0, "اگر خیلی دیر روشن شد (بیرون از پنجرهٔ ۹۰ دقیقه) بریفینگ بی‌موقع نمی‌رود")
finally:
    eng_mod.datetime = _real_dt
    E.run_briefing = _REAL_RUN_BRIEFING     # ← مهم: mock را بردار تا بخش ۴ واقعی اجرا شود
check(E.run_briefing is _REAL_RUN_BRIEFING, "تابع run_briefing به حالت اصلی برگشت")

print()
print("=" * 78)
print("۳) پنل GUI: سیم‌کشی تب‌ها با دادهٔ واقعی")
print("=" * 78)
P.load_fonts()
win = P.MainWindow()
win.show()
app.processEvents()

check(win.tabs.count() == 4, f"۴ تب ساخته شد ({win.tabs.count()})")
check(win.btn_brief.text().startswith("🌅"), f"دکمهٔ بریفینگ وجود دارد: «{win.btn_brief.text()}»")
check(win.btn_brief.isEnabled(), "دکمهٔ بریفینگ فعال است")

# شبیه‌سازی رسیدن نتیجه از موتور (بدون شبکه)
FUND = "🏦 تقویم اقتصادی — تست\n📰 اخبار بازار — تست"
REPORT = "🔎 گزارش تحلیل بازار — تست"
BRIEF = "🌅 بریفینگ صبحگاهی — تست"
win.q.put(("report", REPORT))
win.q.put(("fundamental", FUND))
win.q.put(("briefing", BRIEF))
win._poll_queue()
app.processEvents()

check(REPORT in win.report_view.toPlainText(), "تب «آخرین گزارش کامل» پر شد")
check("تقویم اقتصادی" in win.fund_view.toPlainText(), "تب «تقویم و اخبار» پر شد")
check("بریفینگ صبحگاهی" in win.brief_view.toPlainText(), "تب «بریفینگ» پر شد")
check(win.tabs.currentIndex() == win.TAB_BRIEF, "بعد از بریفینگ، تب بریفینگ فعال می‌شود")
check(win.tabs.tabText(win.TAB_FUND) == "🔔 جدید!", f"علامت «جدید» روی تب: {win.tabs.tabText(win.TAB_FUND)}")

# برچسب‌های وضعیت
win.loop.state.update({"last_run": time.time(), "last_vetoes": ["EURUSD", "GBPUSD"],
                       "calendar_ok": True, "news_count": 18, "alerts_sent": 2})
win._tick()
app.processEvents()
check("وتوی خبری فعال" in win.veto_lbl.text() and "EURUSD" in win.veto_lbl.text(),
      f"برچسب وتو: {win.veto_lbl.text()[:70]}")
check("۱۸ خبر" in win.fund_lbl.text() and "۲ هشدار" in win.fund_lbl.text(),
      f"برچسب فاندامنتال: {win.fund_lbl.text()[:80]}")

win.loop.state.update({"last_vetoes": []})
win._tick()
check("وتوی خبری فعال نیست" in win.veto_lbl.text(), "وقتی وتو نیست، پیام «باز است» نمایش داده می‌شود")

win.close()

print()
print("=" * 78)
print("۴) موتور فاندامنتال در چرخهٔ واقعی (شبکه)")
print("=" * 78)
real_cfg = load_config()
res = E.run_cycle(real_cfg, on_log=lambda m: print("   ", m))
check(res["ok"], f"چرخه موفق بود (errors={res['errors']})")
check(bool(res.get("fundamental_report")), "fundamental_report در نتیجه وجود دارد")
check("تقویم اقتصادی" in res["report"], "گزارش اصلی شامل بخش تقویم است")
check("اخبار بازار" in res["report"], "گزارش اصلی شامل بخش اخبار است")
check(isinstance(res.get("vetoes"), dict), "vetoes برگردانده شد")
print(f"    → calendar_ok={res['calendar_ok']} news_count={res['news_count']} "
      f"vetoes={res['vetoes']} elapsed={res['elapsed']:.1f}s")

b = E.run_briefing(real_cfg, on_log=lambda m: None)
check(b["ok"] and "بریفینگ صبحگاهی" in b["report"], "بریفینگ واقعی ساخته شد")
check(len(b["report"]) > 500, f"بریفینگ محتوای کافی دارد ({len(b['report'])} کاراکتر)")

print()
print("=" * 78)
if FAILS:
    print(f"❌ {len(FAILS)} خطا:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ تست‌های یکپارچگی پاس شدند")
