# -*- coding: utf-8 -*-
"""مسیرهای برنامه — یکسان در حالت اسکریپت (python panel.py) و حالت EXE (PyInstaller)."""
from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "ForexAssistant"
APP_VERSION = "0.2.0"


def is_frozen() -> bool:
    """آیا برنامه به‌صورت EXE بسته‌بندی‌شده در حال اجراست؟"""
    return bool(getattr(sys, "frozen", False))


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


def config_path() -> Path:
    return app_dir() / "config.yaml"


def local_config_path() -> Path:
    """تنظیمات حساس/محلی (توکن تلگرام) — هرگز به گیت‌هاب نمی‌رود."""
    return app_dir() / "config.local.yaml"
