# -*- coding: utf-8 -*-
"""تست کارت تصویری سیگنال دسکتاپ (v0.19.0).

بخش ۱: spec دقیقاً همان رشته‌های js/sharecard.js (وکتورهای مشترک — هر دو
       پلتفرم یک کارت یکسان تولید می‌کنند؛ در smoke_share.js هم قفل شده).
بخش ۲: رندر QPixmap در حالت offscreen.

اجرا: python tests/manual/test_sharecard.py
"""
import os
import pathlib
import sys
from datetime import datetime, timezone

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


from src.report.sharecard import build_share_spec   # noqa: E402

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)   # = ۱۵:۳۰ تهران
SIG = dict(symbol="EURUSD", fa_name="یورو به دلار آمریکا", direction="BUY", stars=5,
           score=10, max_score=11, entry=1.17, sl=1.165, tp=1.18,
           pip=0.0001, is_gold=False, rr=2.0, now=NOW, session_fa="لندن/نیویورک")

print("=" * 70)
print("۱) spec — وکتورهای مشترک با js/sharecard.js")
print("=" * 70)
spec = build_share_spec(SIG, version="0.19.0")
check(spec["brand"] == "ODIN ASSISTANT", "برند")
check(spec["pair"] == "EUR/USD", "جفت‌نمایش")
check(spec["dir"] == "BUY" and spec["dirLabel"] == "سیگنال خرید", "جهت خرید")
check(spec["entry"] == "1.17000" and spec["sl"] == "1.16500" and spec["tp"] == "1.18000",
      "قیمت‌ها لاتین با دقت pip")
check(spec["slDist"] == "۵۰ پیپ" and spec["tpDist"] == "۱۰۰ پیپ", "فاصله‌ها فارسی/پیپ")
check(spec["rr"] == "ریسک به ریسک ۱:۲", "rr")
check(spec["scoreFa"] == "۱۰ از ۱۱" and abs(spec["scorePct"] - 10 / 11) < 1e-9, "امتیاز")
check(spec["stars"] == 5, "ستاره‌ها")
check("شهریور" in spec["jalali"] and "۱۴۰۵" in spec["jalali"] and "دوشنبه" in spec["jalali"],
      "جلالی: " + spec["jalali"])
check(spec["timeTeh"] == "۱۵:۳۰ تهران", "ساعت تهران")
check(spec["session"] == "لندن/نیویورک", "سشن")
check(spec["footerTg"] == "@Khode_Sushian", "تلگرام سازنده")
check("Sushian Khoshkhani" in spec["footerName"], "نام سازنده")
check("پیشنهاد است" in spec["disclaimer"], "سلب مسئولیت")
check(spec["version"] == "v0.19.0", "نسخه")

sell = build_share_spec(dict(SIG, direction="SELL", stars=9))
check(sell["dirLabel"] == "سیگنال فروش" and sell["stars"] == 5, "واریانت فروش + clamp ستاره")

gold = build_share_spec(dict(SIG, symbol="XAUUSD", fa_name="طلا", entry=3650, sl=3672,
                             tp=3606, pip=1, is_gold=True, direction="SELL"))
check(gold["pair"] == "XAU/USD" and gold["entry"] == "3650.0", "طلا: pair/قیمت")
check("$" in gold["slDist"] and "$" in gold["tpDist"], "فاصلهٔ طلا با $")

print("=" * 70)
print("۲) رندر QPixmap (offscreen)")
print("=" * 70)
from PySide6.QtWidgets import QApplication   # noqa: E402
app = QApplication.instance() or QApplication(sys.argv[:1])
from src.report.sharecard import render_card_pixmap   # noqa: E402
pm = render_card_pixmap(spec)
check(not pm.isNull(), "pixmap ساخته شد")
check(pm.width() == 1080 and pm.height() == 1350, "ابعاد ۱۰۸۰×۱۳۵۰ (۴:۵)")
img = pm.toImage()
# کارت مشکی است — گوشهٔ بالا-چپ باید تیره باشد
px = img.pixelColor(8, 8)
check(px.red() < 60 and px.green() < 60 and px.blue() < 60, f"پس‌زمینه تیره ({px.name()})")
# وسط کاشی هدف باید سبز-روشنِ برند داشته باشد (نواحی رنگی جهت)
found_green = any(
    img.pixelColor(x, y).green() > 180 and img.pixelColor(x, y).red() < 180
    for x in range(200, 880, 24) for y in range(600, 900, 24))
check(found_green, "رنگ سبز برند در بدنهٔ کارت دیده می‌شود")

print("=" * 70)
if FAILS:
    print(f"❌ {len(FAILS)} خطا:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ تست‌های کارت تصویری پاس شد")
sys.exit(0)
