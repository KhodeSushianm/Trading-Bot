# -*- coding: utf-8 -*-
"""تست یکپارچگی: پنل GUI (offscreen) + زمان‌بند بریفینگ + سیم‌کشی صفحه‌ها.

به PySide6 و (برای بخش ۴) اینترنت نیاز دارد؛ بنابراین در CI اجرا نمی‌شود.
"""
import os
import pathlib
import sys
import time
from datetime import datetime, timedelta, timezone

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import panel as P
from src import engine as E
from src.config import load_config

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

now = datetime(2026, 9, 21, 5, 0, tzinfo=timezone.utc)
nxt = loop.next_briefing_at({"briefing": {"enabled": True, "times_utc": ["06:30"]}}, now)
check(nxt == datetime(2026, 9, 21, 6, 30, tzinfo=timezone.utc), f"بریفینگ بعدی = {nxt}")
nxt2 = loop.next_briefing_at({"briefing": {"enabled": True, "times_utc": ["06:30"]}},
                             datetime(2026, 9, 21, 7, 0, tzinfo=timezone.utc))
check(nxt2 and nxt2.date().day == 22, f"بعد از گذشت ساعت امروز → فردا ({nxt2})")
check(loop.next_briefing_at({"briefing": {"enabled": False}}, now) is None, "غیرفعال → هیچ")
check(loop.next_briefing_at({"briefing": {"enabled": True, "times_utc": ["25:99"]}}, now) is None,
      "ساعت نامعتبر نادیده گرفته می‌شود")

print()
print("۲) _maybe_briefing در پنجرهٔ catch-up شلیک می‌شود")
calls = {"n": 0}
_REAL = E.run_briefing
E.run_briefing = lambda cfg=None, on_log=None, **kw: (calls.__setitem__("n", calls["n"] + 1)
                                                      or {"ok": True, "report": "BRIEF"})
cfg2 = dict(cfg)
cfg2["briefing"] = {"enabled": True, "times_utc": ["06:30"], "catchup_window_minutes": 90}


class _Fixed(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 9, 21, 7, 0, tzinfo=timezone.utc)


loop2 = E.BotLoop(on_log=lambda m: None, cfg_provider=lambda: cfg2)
E.datetime = _Fixed
try:
    loop2._maybe_briefing(cfg2)
    check(calls["n"] == 1, f"دقیقاً یک بار شلیک شد (n={calls['n']})")
    loop2._maybe_briefing(cfg2)
    check(calls["n"] == 1, "بار دوم شلیک نشد (جلوگیری از تکرار روزانه)")
finally:
    E.datetime = datetime
    E.run_briefing = _REAL
check(E.run_briefing is _REAL, "تابع اصلی بازگردانده شد")

calls2 = {"n": 0}
E.run_briefing = lambda cfg=None, on_log=None, **kw: (calls2.__setitem__("n", calls2["n"] + 1)
                                                      or {"ok": True, "report": "X"})


class _Late(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)


loop3 = E.BotLoop(on_log=lambda m: None, cfg_provider=lambda: cfg2)
E.datetime = _Late
try:
    loop3._maybe_briefing(cfg2)
    check(calls2["n"] == 0, "بیرون از پنجرهٔ ۹۰ دقیقه → بریفینگ بی‌موقع نمی‌رود")
finally:
    E.datetime = datetime
    E.run_briefing = _REAL

print()
print("=" * 78)
print("۳) پنل GUI: ساختار، ناوبری، سیم‌کشی صفحه‌ها")
print("=" * 78)
P.load_fonts()
win = P.MainWindow(show_splash=False)
win.show()
app.processEvents()

check(win.pages.count() == 7, f"۷ صفحه ساخته شد ({win.pages.count()})")
check(len(win.nav._items) == 7, f"ریل ناوبری ۷ آیتم دارد ({len(win.nav._items)})")   # noqa: SLF001
check(win.user_name == "سوشیان", f"نام کاربر از config خوانده شد: {win.user_name}")
check("خوش اومدی سوشیان" in win.greet_lbl.text(), f"چیپ خوش‌آمد: {win.greet_lbl.text()}")

# ناوبری صفحه را عوض می‌کند
win.nav._select(win.TAB_SIGNAL)      # noqa: SLF001
app.processEvents()
check(win.pages.currentIndex() == win.TAB_SIGNAL, "کلیک روی ناوبری صفحه را عوض می‌کند")
win.nav._select(win.TAB_DASH)        # noqa: SLF001
app.processEvents()

# پر شدن صفحه‌ها از صف پیام‌ها
REPORT, FUND, BRIEF, SIGNAL = "گزارش تست", "تقویم تست", "بریفینگ تست", "🔴 سیگنال فروش — EUR/USD تست"
win.q.put(("report", REPORT))
win.q.put(("fundamental", FUND))
win.q.put(("briefing", BRIEF))
win.q.put(("signal", SIGNAL))
win._poll_queue()
app.processEvents()
check(REPORT in win.report_view.toPlainText(), "صفحهٔ گزارش کامل پر شد")
check(FUND in win.fund_view.toPlainText(), "صفحهٔ تقویم و اخبار پر شد")
check(BRIEF in win.brief_view.toPlainText(), "صفحهٔ بریفینگ پر شد")
check(SIGNAL in win.sig_view.toPlainText(), "صفحهٔ سیگنال‌ها پر شد")
check(win.pages.currentIndex() == win.TAB_SIGNAL, "آخرین رویداد (سیگنال) صفحه‌اش را باز کرد")
check(win.toast.isVisibleTo(win.centralWidget()) or win.toast.isVisible(),
      "برای سیگنال جدید Toast نمایش داده شد")

# داشبورد از state موتور پر می‌شود
win.loop.state.update({
    "last_run": time.time(), "last_vetoes": ["XAUUSD"], "news_count": 18,
    "signals_total": 5,
    "last_signals": [{"symbol": "GBPUSD", "direction": "SELL", "score": 8,
                      "max_score": 11, "sent": True},
                     {"symbol": "EURUSD", "direction": "BUY", "score": 7,
                      "max_score": 11, "sent": False}],
    "ranking": [("CHF", 0.32), ("USD", -0.13), ("JPY", -0.58)],
    "upcoming": [{"title_fa": "نرخ بهره فدرال رزرو", "country_fa": "آمریکا",
                  "country": "USD", "impact": "HIGH", "when": "", "minutes": 240}],
})
win._tick()
app.processEvents()
check("GBPUSD" in win.dash_signals.toPlainText() and "EURUSD" in win.dash_signals.toPlainText(),
      "داشبورد: آخرین سیگنال‌ها فهرست شد")
check("ارسال نشد" in win.dash_signals.toPlainText(), "داشبورد: سیگنال ارسال‌نشد علامت خورد")
check("نرخ بهره فدرال رزرو" in win.dash_events.toPlainText(), "داشبورد: رویداد پیش‌رو نمایش داده شد")
check(len(win.strength._data) == 3, f"داشبورد: نوارهای قدرت داده گرفتند ({len(win.strength._data)})")   # noqa: SLF001
check("XAUUSD" in win.veto_lbl.text(), f"داشبورد: برچسب وتو ({win.veto_lbl.text()})")
check(win.st_score._num.text() == "۸/۱۱", f"کارت امتیاز: {win.st_score._num.text()}")   # noqa: SLF001
check(win.st_news._num.text() == "۱۸", f"کارت خبر: {win.st_news._num.text()}")   # noqa: SLF001

# قرص وضعیت
win.loop._thread = None      # noqa: SLF001
win._tick()
check(win.status_pill is not None, "قرص وضعیت موجود است")

win.close()

print()
print("=" * 78)
print("۴) چرخهٔ واقعی (شبکه) از طریق موتور")
print("=" * 78)
res = E.run_cycle(load_config(), on_log=lambda m: None)
check(res["ok"], f"چرخه موفق (errors={res['errors']})")
check("ranking" in res and "upcoming" in res and "symbols_summary" in res,
      "دادهٔ ساختاریافتهٔ داشبورد در نتیجهٔ چرخه هست")
check(isinstance(res.get("signals"), list), "فهرست سیگنال‌ها در نتیجه هست")

print()
print("=" * 78)
if FAILS:
    print(f"❌ {len(FAILS)} خطا:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ تست‌های یکپارچگی پاس شدند")
