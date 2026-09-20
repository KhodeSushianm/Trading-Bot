# -*- coding: utf-8 -*-
"""مسیرهای برنامه — یکسان در حالت اسکریپت (python panel.py) و حالت EXE (PyInstaller)."""
from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "ForexAssistant"
APP_VERSION = "0.7.2"


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

    همه فایل‌های قابل ویرایش کاربر (config.yaml، config.local.yaml، logs/)
    کنار خود برنامه نگه داشته می‌شوند تا EXE کاملاً قابل‌حمل باشد.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_dir() -> Path:
    """پوشه فایل‌های بسته‌بندی‌شده (فونت، آیکون، config پیش‌فرض).

    در حالت EXE، PyInstaller آن‌ها را در مسیر موقت _MEIPASS استخراج می‌کند.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", str(app_dir())))
    return app_dir()


def fonts_dirs() -> list[Path]:
    """فونت‌ها به ترتیب اولویت: پوشه fonts کنار برنامه (فونت کاربر، مثلاً ایران‌سنس)
    سپس فونت‌های بسته‌بندی‌شده (وزیرمتن)."""
    return [app_dir() / "fonts", bundled_dir() / "assets" / "fonts"]


def logs_dir() -> Path:
    d = app_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    """پوشه کش داده (تقویم اقتصادی، اخبار، وضعیت هشدارها).

    محتوای این پوشه قابل بازسازی است و در .gitignore قرار دارد.
    """
    d = app_dir() / "data" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sent_alerts_path() -> Path:
    """فایل وضعیت هشدارهای ارسال‌شده (تا یک رویداد دو بار هشدار نگیرد)."""
    return cache_dir() / "sent_alerts.json"


def config_path() -> Path:
    return app_dir() / "config.yaml"


def local_config_path() -> Path:
    """تنظیمات حساس/محلی (توکن تلگرام) — هرگز به گیت‌هاب نمی‌رود."""
    return app_dir() / "config.local.yaml"
