# -*- coding: utf-8 -*-
"""تست صفحهٔ تنظیمات پنل ویندوز — آینهٔ نسخهٔ اندروید (v0.8.1).

پوشش:
  ۱) ساخت ویجت‌ها: سوئیچ‌ها، قدم‌شمارها، ورودی نام، صفحه داخل اسکرول
  ۲) ماندگاری: هر تغییر فوری در config.local.yaml می‌نشیند و load_config
     تازه همان را می‌بیند (مسیری که BotLoop هر چرخه طی می‌کند)
  ۳) اثر آنی: نام نمایشی در هدر/آواتار، انیمیشن‌ها در effects
  ۴) محافظ‌ها: guard هنگام بارگذاری، clamp قدم‌شمار، اولویت local بر yaml
  ۵) پاک‌کردن کش تقویم و بازنشانی تنظیمات (تلگرام/ژورنال دست‌نخورده)
  ۶) رندر: صفحهٔ تنظیمات خالی نیست و اثر گرافیکی باقی نمی‌ماند

داده‌ها در پوشهٔ temp نگه داشته می‌شوند تا config.local.yaml واقعیِ کاربر
(توکن تلگرام!) هرگز لمس نشود.

به PySide6 نیاز دارد؛ در CI اجرا نمی‌شود (مثل بقیهٔ tests/manual).
اجرا:  python tests/manual/test_settings_ui.py
"""
import os
import pathlib
import shutil
import sys
import tempfile
import time

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# پوشهٔ دادهٔ موقت — قبل از هر ایمپورتی از src که data_dir را کش کند
_TMP = tempfile.mkdtemp(prefix="odin-settings-test-")
_real_cfg = _ROOT / "config.yaml"
if _real_cfg.exists():
    shutil.copyfile(_real_cfg, str(pathlib.Path(_TMP) / "config.yaml"))
os.environ["ODIN_DATA_DIR"] = _TMP

from PySide6.QtGui import QFont                     # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit, QScrollArea  # noqa: E402

import panel as P                                   # noqa: E402
from src import app_paths                           # noqa: E402
from src.config import load_config, save_local_config  # noqa: E402
from src.ui import effects                          # noqa: E402
from src.ui.widgets import Stepper, ToggleSwitch    # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


def pump(app, seconds=0.35):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        app.thread().msleep(10)


app = QApplication(sys.argv[:1])
app.setStyle("Fusion")
app.setLayoutDirection(P.Qt.RightToLeft)
fam = P.load_fonts()
app.setFont(QFont(fam, 11))
app.setStyleSheet(P.build_qss(fam, check_img=P._check_img()))   # noqa: SLF001

win = P.MainWindow(show_splash=False)
win.resize(1280, 900)
win.show()
pump(app)

base = load_config()

print("=" * 78)
print("۱) ساختار صفحهٔ تنظیمات")
print("=" * 78)
page = win.pages.widget(win.TAB_SETTINGS)
check(isinstance(page, QScrollArea) and page.objectName() == "pagescroll",
      "صفحهٔ تنظیمات داخل ظرف اسکرول است (محتوای بلند)")
check(isinstance(win.set_name, QLineEdit), "ورودی نام نمایشی ساخته شد")
expect_sw = {"judge_enabled", "fund_enabled", "alerts_enabled", "news_enabled",
             "tv_enabled", "briefing_enabled", "journal_enabled", "both_touch",
             "splash", "animations",
             *(f"veto.{k}" for k in P.VETO_KEYS)}
check(expect_sw <= set(win.set_switches),
      f"همهٔ {len(expect_sw)} سوئیچ ساخته شدند")
check(all(isinstance(s, ToggleSwitch) for s in win.set_switches.values()),
      "سوئیچ‌ها از نوع ToggleSwitch (آینهٔ اندروید) هستند")
check({"min_score", "max_signals_per_cycle", "interval_minutes"}
      <= set(win.set_steppers), "هر سه قدم‌شمار ساخته شدند")
check(all(isinstance(s, Stepper) for s in win.set_steppers.values()),
      "قدم‌شمارها از نوع Stepper هستند")

print("=" * 78)
print("۲) بارگذاری مقادیر از config (بدون نوشتن ناخواسته)")
print("=" * 78)
before_hash = (app_paths.local_config_path().read_bytes()
               if app_paths.local_config_path().exists() else b"")
win.nav._select(win.TAB_SETTINGS)                   # noqa: SLF001
pump(app)
after_hash = (app_paths.local_config_path().read_bytes()
              if app_paths.local_config_path().exists() else b"")
check(before_hash == after_hash,
      "بازکردن صفحهٔ تنظیمات چیزی نمی‌نویسد (guard درست کار می‌کند)")
check(win.set_steppers["min_score"].value() == base["judge"]["min_score"],
      f"آستانهٔ داور از config بارگذاری شد ({base['judge']['min_score']})")
check(win.set_steppers["interval_minutes"].value()
      == base["loop"]["interval_minutes"], "فاصلهٔ حلقه از config بارگذاری شد")
check(win.set_name.text() == base["ui"]["user_name"], "نام نمایشی بارگذاری شد")
check(win.set_switches["judge_enabled"].isChecked() == base["judge"]["enabled"],
      "وضعیت داور بارگذاری شد")

print("=" * 78)
print("۳) نام نمایشی — اثر آنی + ماندگاری")
print("=" * 78)
win.set_name.setText("  آرش  ")
win._on_name_edited()                               # noqa: SLF001
pump(app, 0.2)
check(win.user_name == "آرش", "نام trim شد و در وضعیت پنل نشست")
check("سلام آرش" in win.greet_lbl.text(), "سلام هدر آنی به‌روز شد")
check(win.avatar.text() == "آ", "آواتار حرف اول نام تازه است")
check(load_config()["ui"]["user_name"] == "آرش", "نام در config.local.yaml نشست")
win.set_name.setText("   ")
win._on_name_edited()                               # noqa: SLF001
check(win.set_name.text() == "سوشیان" and win.user_name == "سوشیان",
      "نام خالی → بازگشت به پیش‌فرض «سوشیان»")

print("=" * 78)
print("۴) سوئیچ‌ها — ذخیرهٔ فوری و اولویت بر config.yaml")
print("=" * 78)
for key, section, cfg_key in (
        ("judge_enabled", "judge", "enabled"),
        ("fund_enabled", "fundamental", "enabled"),
        ("news_enabled", "news", "enabled"),
        ("tv_enabled", "tradingview", "enabled"),
        ("briefing_enabled", "briefing", "enabled"),
        ("journal_enabled", "journal", "enabled"),
        ("both_touch", "journal", "conservative_both_touch"),
        ("alerts_enabled", "fundamental", "alerts_enabled")):
    s = win.set_switches[key]
    s.setChecked(not s.isChecked())
    pump(app, 0.12)
    got = (load_config().get(section) or {}).get(cfg_key)
    check(got == s.isChecked(),
          f"سوئیچ «{key}» → {section}.{cfg_key} = {got}")
    s.setChecked(not s.isChecked())                 # برگردان
    pump(app, 0.12)

for vk in P.VETO_KEYS:
    s = win.set_switches[f"veto.{vk}"]
    s.setChecked(False)
    pump(app, 0.12)
    got = load_config()["judge"]["veto"][vk]
    check(got is False, f"وتوی «{vk}» خاموش و ذخیره شد")
    s.setChecked(True)
    pump(app, 0.12)
check(all(load_config()["judge"]["veto"][k] is True for k in P.VETO_KEYS),
      "همهٔ وتوها به حالت روشن برگشتند")

print("=" * 78)
print("۵) قدم‌شمارها — clamp و ذخیره")
print("=" * 78)
sc = win.set_steppers["min_score"]
sc.setValue(99)
pump(app, 0.12)
check(sc.value() == 10 and load_config()["judge"]["min_score"] == 10,
      "آستانهٔ داور در سقف ۱۰ clamp شد و ذخیره شد")
sc.setValue(-5)
pump(app, 0.12)
check(sc.value() == 4 and load_config()["judge"]["min_score"] == 4,
      "آستانهٔ داور در کف ۴ clamp شد")
sc.setValue(base["judge"]["min_score"])
pump(app, 0.12)

iv = win.set_steppers["interval_minutes"]
iv.setValue(45)
pump(app, 0.12)
check(load_config()["loop"]["interval_minutes"] == 45,
      "فاصلهٔ حلقه ۴۵ دقیقه ذخیره شد")
iv.setValue(base["loop"]["interval_minutes"])
pump(app, 0.12)

mx = win.set_steppers["max_signals_per_cycle"]
mx.setValue(5)
pump(app, 0.12)
check(load_config()["judge"]["max_signals_per_cycle"] == 5,
      "سقف سیگنال هر چرخه ذخیره شد")
mx.setValue(base["judge"]["max_signals_per_cycle"])
pump(app, 0.12)

print("=" * 78)
print("۶) ظاهر — انیمیشن‌ها آنی اعمال می‌شوند")
print("=" * 78)
anim = win.set_switches["animations"]
anim.setChecked(False)
pump(app, 0.15)
check(effects.ANIMATIONS is False, "خاموش‌کردن انیمیشن → effects.ANIMATIONS=False")
anim.setChecked(True)
pump(app, 0.15)
check(effects.ANIMATIONS is True, "روشن‌کردن انیمیشن → effects.ANIMATIONS=True")

print("=" * 78)
print("۷) پاک‌کردن کش و بازنشانی تنظیمات")
print("=" * 78)
cache_f = app_paths.cache_dir() / "calendar.json"
cache_f.write_text('[{"x":1}]', encoding="utf-8")
win._on_clear_cache()                               # noqa: SLF001
check(not cache_f.exists(), "کش تقویم پاک شد")
sent = app_paths.cache_dir() / "sent_signals.json"
sent.write_text("{}", encoding="utf-8")
win._on_clear_cache()                               # noqa: SLF001
check(sent.exists(), "کنترل اسپم سیگنال (sent_signals) دست‌نخورده ماند")

win.set_name.setText("کاربر تست")
win._on_name_edited()                               # noqa: SLF001
win.set_switches["judge_enabled"].setChecked(False)
win.set_switches["veto.weekend"].setChecked(False)
win.set_steppers["min_score"].setValue(9)
pump(app, 0.2)
save_local_config({"telegram": {"bot_token": "T0KEN", "chat_id": "42"}})
win._reset_settings_now()                           # noqa: SLF001
pump(app, 0.2)
cfg3 = load_config()
check(cfg3["judge"]["enabled"] is True, "بازنشانی: داور دوباره فعال")
check(cfg3["judge"]["min_score"] == base["judge"]["min_score"],
      "بازنشانی: آستانه به پیش‌فرض برگشت")
check(cfg3["judge"]["veto"]["weekend"] is True, "بازنشانی: وتوی آخر هفته برگشت")
check(cfg3["ui"]["user_name"] == base["ui"]["user_name"],
      "بازنشانی: نام به پیش‌فرض برگشت")
check(win.user_name == base["ui"]["user_name"]
      and base["ui"]["user_name"] in win.greet_lbl.text(),
      "بازنشانی: هدر هم به‌روز شد")
check(win.set_switches["judge_enabled"].isChecked(),
      "بازنشانی: ویجت‌ها از config تازه پر شدند")
check(win.set_steppers["min_score"].value() == base["judge"]["min_score"],
      "بازنشانی: قدم‌شمار هم برگشت")
check(cfg3["telegram"]["bot_token"] == "T0KEN" and cfg3["telegram"]["chat_id"] == "42",
      "بازنشانی: تلگرام دست‌نخورده ماند")
check((app_paths.local_config_path()).exists(),
      "فایل محلی هنوز هست (فقط کلیدهای مدیریت‌شده حذف شدند)")

print("=" * 78)
print("۸) رندر صفحهٔ تنظیمات — بدون باگ «سیاه/خالی»")
print("=" * 78)
win.nav._select(win.TAB_SETTINGS)                   # noqa: SLF001
deadline = time.time() + 2.5
while time.time() < deadline and page.graphicsEffect() is not None:
    app.processEvents()
    app.thread().msleep(10)
check(page.graphicsEffect() is None, "پس از fade هیچ اثر گرافیکی باقی نماند")
img = page.grab().toImage()
bgc = img.pixelColor(4, 4)
total = diff = 0
for y in range(0, img.height(), 6):
    for x in range(0, img.width(), 6):
        total += 1
        if img.pixelColor(x, y) != bgc:
            diff += 1
check(diff / max(total, 1) > 0.02,
      f"صفحهٔ تنظیمات محتوا رندر کرد (نسبت {diff / max(total, 1):.3f})")

# اسکرول عمودی باید ممکن باشد (محتوا از ویوپورت بلندتر است)
vp_h = page.viewport().height()
content_h = page.widget().sizeHint().height()
check(content_h > 100, f"محتوای صفحه اندازهٔ معقول دارد ({content_h}px)")

win.close()
shutil.rmtree(_TMP, ignore_errors=True)

print()
print("=" * 78)
if FAILS:
    print(f"❌ {len(FAILS)} خطا:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ صفحهٔ تنظیمات کامل سالم است — آینهٔ اندروید روی ویندوز")
