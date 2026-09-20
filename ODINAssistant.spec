# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — ساخت ODINAssistant.exe (تک‌فایلی، بدون کنسول)
from PyInstaller.utils.hooks import collect_submodules

hidden = []
hidden += collect_submodules("yfinance")
hidden += collect_submodules("tradingview_ta")
# feedparser داخل تابع و به‌صورت lazy ایمپورت می‌شود؛ برای اطمینان صریحاً جمع‌آوری می‌کنیم
# (ماژول‌های src.* همه استاتیک ایمپورت می‌شوند و خود PyInstaller پیدایشان می‌کند)
hidden += collect_submodules("feedparser")
# آیکون‌های SVG داخل تابع و به‌صورت lazy ایمپورت می‌شوند
hidden += ["PySide6.QtSvg"]

a = Analysis(
    ["panel.py"],
    pathex=["."],
    binaries=[],
    datas=[("assets", "assets"), ("config.yaml", "assets")],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "tkinter", "PyQt5", "PyQt6", "IPython", "notebook"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ODINAssistant",
    version="installer/version_info.txt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon="assets/icon.ico",
)
