# -*- coding: utf-8 -*-
"""تست رگرسیون «صفحهٔ سیاه/خالی» — همهٔ صفحه‌ها باید محتوا رندر کنند.

باگ اصلی نسخهٔ ۰٫۵ این بود که QGraphicsOpacityEffect پس از انیمیشن fade روی
صفحه باقی می‌ماند و Qt فرزندان را در بافر آف‌اسکرین نگه می‌داشت؛ نتیجه: صفحه
سیاه/کهنه می‌ماند تا کاربر پنجره را درگ/resize کند.

این تست برای هر ۷ صفحه بررسی می‌کند:
  ۱) پس از پایان fade، هیچ QGraphicsOpacityEffect باقی نمانده باشد
  ۲) صفحه واقعاً پیکسل‌های غیر از پس‌زمینه داشته باشد (یعنی محتوا کشیده شده)
  ۳) یک به‌روزرسانی متنِ بعدی هم بدون درگ/resize دیده شود (همان سناریوی باگ)

به PySide6 نیاز دارد؛ در CI اجرا نمی‌شود.
"""
import os
import pathlib
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

import panel as P

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


def drain(app, win, widget, timeout_s=2.5):
    """صبر کن تا انیمیشن تمام و اثر حذف شود."""
    deadline = time.time() + timeout_s
    while time.time() < deadline and widget.graphicsEffect() is not None:
        app.processEvents()
        app.thread().msleep(10)
    app.processEvents()


def non_bg_fraction(img, step=6):
    bg = img.pixelColor(4, 4)
    total = 0
    diff = 0
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            total += 1
            if img.pixelColor(x, y) != bg:
                diff += 1
    return diff / max(total, 1)


app = QApplication(sys.argv[:1])
app.setStyle("Fusion")
app.setLayoutDirection(P.Qt.RightToLeft)
fam = P.load_fonts()
app.setFont(QFont(fam, 11))
app.setStyleSheet(P.build_qss(fam))

win = P.MainWindow(show_splash=False)
win.resize(QSize(1200, 880))
win.show()
app.processEvents()

# محتوا بگذار تا صفحه‌ها خالی نباشند
win.report_view.setPlainText("گزارش نمونه\nسطر دوم برای رندر")
win.log_view.setPlainText("لاگ نمونه")
win.sig_view.setPlainText("سیگنال نمونه")
win.fund_view.setPlainText("تقویم نمونه")
win.brief_view.setPlainText("بریفینگ نمونه")
win.loop.state.update({"last_run": time.time(), "news_count": 3,
                       "ranking": [("CHF", 0.3), ("JPY", -0.4)],
                       "last_signals": [], "upcoming": []})

print("=" * 78)
print("بررسی رندر و پاک‌سازی اثر برای همهٔ صفحه‌ها")
print("=" * 78)
names = ["داشبورد", "سیگنال‌ها", "گزارش کامل", "تقویم و اخبار",
         "بریفینگ", "گزارش زنده", "تنظیمات"]
for idx, name in enumerate(names):
    win.nav._select(idx)                       # noqa: SLF001
    page = win.pages.widget(idx)
    drain(app, win, page)

    # ۱) اثر باقی‌مانده؟
    check(page.graphicsEffect() is None, f"[{name}] پس از fade هیچ اثری باقی نمانده")

    # ۲) محتوا رندر شد؟
    frac = non_bg_fraction(page.grab().toImage())
    check(frac > 0.004, f"[{name}] محتوا رندر شد (نسبت پیکسل غیرپس‌زمینه {frac:.3f})")

    # ۳) سناریوی باگ: متن را بعداً عوض کن و بدون درگ بررسی کن دیده می‌شود
    if idx == P.MainWindow.TAB_REPORT:
        win.report_view.setPlainText("متن به‌روزشده بدون درگ ✅")
        app.processEvents()
        img = win.pages.widget(idx).grab().toImage()
        check(non_bg_fraction(img) > 0.004,
              f"[{name}] به‌روزرسانی متن بدون درگ/resize دیده می‌شود")

# ناوبری برگردد به داشبورد و داشبورد هم تمیز باشد
win.nav._select(P.MainWindow.TAB_DASH)
drain(app, win, win.pages.widget(P.MainWindow.TAB_DASH))
check(win.pages.widget(P.MainWindow.TAB_DASH).graphicsEffect() is None,
      "[داشبورد] اثر باقی‌مانده ندارد")

# Toast هم باید بعد از بسته‌شدن اثرش را پاک کند
win.toast.show_message("عنوان تست", "بدنه تست", "info")
app.processEvents()
win.toast.dismiss()
deadline = time.time() + 2.0
while time.time() < deadline and (win.toast.isVisible() or win.toast.graphicsEffect() is not None):
    app.processEvents()
    app.thread().msleep(10)
check(win.toast.graphicsEffect() is None, "[Toast] پس از بسته‌شدن اثری باقی نگذاشت")
check(not win.toast.isVisible(), "[Toast] پس از dismiss پنهان شد")

win.close()
print()
print("=" * 78)
if FAILS:
    print(f"❌ {len(FAILS)} خطا:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ صفحه‌ها بدون باگ «سیاه/خالی» رندر می‌شوند")
