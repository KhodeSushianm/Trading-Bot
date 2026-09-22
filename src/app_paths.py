# -*- coding: utf-8 -*-
"""مسیرهای برنامه — یکسان در حالت اسکریپت (python panel.py) و حالت EXE (PyInstaller).

از نسخهٔ ۰٫۸ دو حالت اجرا داریم:
  • پرتابل : EXE تک‌فایلی در هر پوشه‌ای که کاربر بخواهد؛ همهٔ داده‌ها کنار خودش
  • نصب‌شده : نصب‌کنندهٔ رسمی (Inno Setup) برنامه را در Program Files می‌گذارد و
             داده‌های کاربر به «پوشهٔ داده‌ها» (%APPDATA%\\ODIN Assistant) می‌روند
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ODIN Assistant"          # برند نمایشی (عنوان پنجره، Splash، پیام‌ها)
PRODUCT = "ODINAssistant"            # نام فنی بدون فاصله (EXE، پوشهٔ نصب، کلیدها)
APP_VERSION = "0.19.1"

# متغیر محیطی برای نشاندن اجباری پوشهٔ داده‌ها (تست‌ها و حالت‌های خاص)
DATA_DIR_ENV = "ODIN_DATA_DIR"
# فایل کنار EXE که حالت پرتابل را حتی داخل Program Files اجبار می‌کند
PORTABLE_MARKER = ".portable"
# فایل نصب‌کننده کنار EXE که حالت «نصب‌شده» را قطعی می‌کند
INSTALLED_MARKER = ".installed"
# نشانه‌های نسخه‌های پرتابل قدیمی (داده کنار EXE داشتند)
_LEGACY_MARKERS = ("config.local.yaml", "config.yaml", "logs")

_data_dir_cache: "Path | None" = None


def is_frozen() -> bool:
    """آیا برنامه به‌صورت EXE بسته‌بندی‌شده در حال اجراست؟"""
    return bool(getattr(sys, "frozen", False))


def fix_console_encoding() -> None:
    """کنسول را روی UTF-8 بگذار تا متن فارسی و ایموجی استثنا پرتاب نکنند.

    چرا لازم است:
      کدپیش‌فرض کنسول ویندوز cp1252 است. بدون این تابع، اولین print فارسی
      (مثلاً «[auto] منابع داده فعال: yahoo» در لایهٔ داده) روی ویندوز
      UnicodeEncodeError می‌دهد. چون آن print داخل connect() و داخل try/except
      موتور است، خطا بی‌صدا به «اتصال به منبع داده ناموفق» ترجمه می‌شد و
      کل لایهٔ داده از کار می‌افتاد.

      در EXE پنجره‌ای (console=False) این مشکل دیده نمی‌شد، چون PyInstaller
      خروجی را دور می‌ریزد؛ ولی در اجرای «python panel.py» روی کنسول واقعی
      و در GitHub Actions کاملاً فعال است.

    بی‌خطر و چندبار‌فراخوانی‌شدنی است.
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:                      # حالت EXE بی‌کنسول
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
            continue
        except Exception:
            pass
        try:                                    # جریان‌های بدون reconfigure
            import io
            buf = getattr(stream, "buffer", None)
            if buf is not None:
                setattr(sys, name, io.TextIOWrapper(buf, encoding="utf-8",
                                                    errors="replace", line_buffering=True))
        except Exception:
            pass


def app_dir() -> Path:
    """پوشه کنار فایل اجرایی (EXE) یا ریشه پروژه در حالت توسعه.

    فقط برای فایل‌های خود برنامه؛ فایل‌های قابل‌نوشتن کاربر را data_dir() می‌دهد.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _is_writable(d: Path) -> bool:
    """آزمایش نوشتن واقعی (ساخت پوشه + فایل موقت) — قابل‌اتکا روی ویندوز."""
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".wtest"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _roaming_appdata() -> Path:
    """%APPDATA%\\ODIN Assistant — جای استاندارد داده‌های کاربر در حالت نصب."""
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_NAME


def clear_data_dir_cache() -> None:
    """کش data_dir را خالی می‌کند (فقط برای تست‌ها)."""
    global _data_dir_cache
    _data_dir_cache = None


def data_dir() -> Path:
    """پوشهٔ داده‌های قابل‌نوشتن کاربر: config، config.local، logs، کش، ژورنال، فونت.

    ترتیب تشخیص در حالت EXE:
      ۱) متغیر محیطی ODIN_DATA_DIR (تست‌ها)
      ۲) فایل «.portable» کنار EXE  → اجباراً پرتابل (حتی داخل Program Files)
      ۳) فایل «.installed» کنار EXE → حالت نصب‌شده → %APPDATA%\\ODIN Assistant
      ۴) نشانه‌های پرتابل قدیمی (config.yaml/config.local.yaml/logs) و پوشه قابل‌نوشتن
         → همان پوشهٔ کنار EXE (ارتقای بدون درد نسخه‌های ≤۰٫۷)
      ۵) پوشهٔ کنار EXE قابل‌نوشتن  → پرتابل (EXE تازه در هر پوشه‌ای)
      ۶) وگرنه (کپی دستی در پوشهٔ محافظت‌شده) → %APPDATA%\\ODIN Assistant

    در حالت توسعه (python panel.py) همیشه ریشهٔ پروژه است.
    """
    global _data_dir_cache
    if _data_dir_cache is not None:
        return _data_dir_cache
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        d = Path(override).resolve()
    elif not is_frozen():
        d = app_dir()
    else:
        exe_dir = app_dir()
        if (exe_dir / PORTABLE_MARKER).exists():
            d = exe_dir
        elif (exe_dir / INSTALLED_MARKER).exists():
            d = _roaming_appdata()
        elif (any((exe_dir / m).exists() for m in _LEGACY_MARKERS)
              and _is_writable(exe_dir)):
            d = exe_dir
        elif _is_writable(exe_dir):
            d = exe_dir
        else:
            d = _roaming_appdata()
    d.mkdir(parents=True, exist_ok=True)
    _data_dir_cache = d
    return d


def bundled_dir() -> Path:
    """پوشه فایل‌های بسته‌بندی‌شده (فونت، آیکون، config پیش‌فرض).

    در حالت EXE، PyInstaller آن‌ها را در مسیر موقت _MEIPASS استخراج می‌کند.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", str(app_dir())))
    return app_dir()


def fonts_dirs() -> list[Path]:
    """فونت‌ها به ترتیب اولویت: پوشه fonts داخل پوشهٔ داده‌ها (فونت کاربر،
    مثلاً ایران‌سنس) سپس فونت‌های بسته‌بندی‌شده (وزیرمتن)."""
    return [data_dir() / "fonts", bundled_dir() / "assets" / "fonts"]


def logs_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    """پوشه کش داده (تقویم اقتصادی، اخبار، وضعیت هشدارها).

    محتوای این پوشه قابل بازسازی است و در .gitignore قرار دارد.
    """
    d = data_dir() / "data" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sent_alerts_path() -> Path:
    """فایل وضعیت هشدارهای ارسال‌شده (تا یک رویداد دو بار هشدار نگیرد)."""
    return cache_dir() / "sent_alerts.json"


def config_path() -> Path:
    return data_dir() / "config.yaml"


def local_config_path() -> Path:
    """تنظیمات حساس/محلی (توکن تلگرام) — هرگز به گیت‌هاب نمی‌رود."""
    return data_dir() / "config.local.yaml"
