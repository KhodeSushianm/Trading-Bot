# -*- coding: utf-8 -*-
"""بارگذاری پیکربندی.

- config.yaml       : تنظیمات اصلی (قابل ویرایش توسط کاربر)
- config.local.yaml : تنظیمات حساس/محلی مثل توکن تلگرام — روی config.yaml ادغام
                      می‌شود و هرگز در گیت کامیت نمی‌شود (.gitignore)

در حالت EXE، اگر config.yaml کنار برنامه نباشد، نسخه پیش‌فرض بسته‌بندی‌شده
به‌صورت خودکار ساخته می‌شود (تجربه «دانلود و اجرا»).
"""
from __future__ import annotations

import os
import shutil

import yaml

from . import app_paths

# حداقل پیکربندی اضطراری (اگر فایل بسته‌بندی‌شده هم پیدا نشد)
_MINIMAL_DEFAULT = """data_source: auto
symbols:
  - {name: EURUSD, fa: "یورو به دلار آمریکا", yahoo: "EURUSD=X", td: "EUR/USD",
     tv: {screener: forex, exchange: FX, symbol: EURUSD}, base: EUR, quote: USD, pip: 0.0001}
analysis: {ema_fast: 50, ema_slow: 200, adx_period: 14, adx_min_trend: 20,
           rsi_period: 14, atr_period: 14, swing_window: 5, strength_lookback_h1: 24}
tradingview: {enabled: true, timeframe: 4h}
fundamental: {enabled: true, cache_ttl_minutes: 30, horizon_hours: 48,
              veto_minutes_before: 30, alerts_enabled: true, alert_before_minutes: 30}
news: {enabled: true, max_age_hours: 30, min_score: 2, max_items_per_feed: 12, max_total: 18}
briefing: {enabled: true, times_utc: ["06:30"], horizon_hours: 24, catchup_window_minutes: 90}
judge: {enabled: true, min_score: 7, max_signals_per_cycle: 3}
telegram: {send_reports: true, bot_token: "", chat_id: ""}
loop: {interval_minutes: 15}
"""


def ensure_config_file() -> None:
    """اگر config.yaml کنار برنامه نبود، از نسخه بسته‌بندی‌شده کپی کن."""
    p = app_paths.config_path()
    if p.exists():
        return
    bundled = app_paths.bundled_dir() / "assets" / "config.yaml"
    try:
        if bundled.exists():
            shutil.copyfile(bundled, p)
        else:
            p.write_text(_MINIMAL_DEFAULT, encoding="utf-8")
    except Exception:
        pass  # در بدترین حالت load_config خطای واضح می‌دهد


def _deep_merge(base: dict, over: dict) -> dict:
    """ادغام عمیق over داخل base (مقادیر over برنده می‌شوند)."""
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: str | None = None) -> dict:
    ensure_config_file()
    cfg_file = path or app_paths.config_path()
    if not os.path.exists(cfg_file):
        raise FileNotFoundError(f"فایل پیکربندی پیدا نشد: {cfg_file}")
    with open(cfg_file, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # ادغام تنظیمات محلی (توکن تلگرام و ...)
    lp = app_paths.local_config_path()
    if lp.exists():
        try:
            with open(lp, encoding="utf-8") as f:
                cfg = _deep_merge(cfg, yaml.safe_load(f) or {})
        except Exception:
            pass  # فایل محلی خراب بود — با تنظیمات اصلی ادامه بده

    for key in ("data_source", "symbols", "analysis"):
        if key not in cfg:
            raise ValueError(f"کلید الزامی «{key}» در config.yaml وجود ندارد")
    if not isinstance(cfg["symbols"], list) or not cfg["symbols"]:
        raise ValueError("«symbols» باید فهرستی غیرخالی از نمادها باشد")
    for sym in cfg["symbols"]:
        for field in ("name", "base", "quote", "pip"):
            if field not in sym:
                raise ValueError(f"نماد {sym.get('name', '?')} فیلد «{field}» ندارد")

    cfg.setdefault("history", {})
    cfg.setdefault("twelvedata", {})
    cfg.setdefault("tradingview", {"enabled": True, "timeframe": "4h"})
    cfg.setdefault("telegram", {"send_reports": True, "bot_token": "", "chat_id": ""})
    cfg.setdefault("loop", {"interval_minutes": 15})
    cfg["loop"].setdefault("interval_minutes", 15)

    # ── مرحله ۲: فاندامنتال، اخبار، بریفینگ ────────────────────
    f = cfg.setdefault("fundamental", {})
    for k, v in (("enabled", True),
                 ("source_url", "https://nfs.faireconomy.media/ff_calendar_thisweek.json"),
                 ("cache_ttl_minutes", 30), ("horizon_hours", 48),
                 ("veto_minutes_before", 30), ("alerts_enabled", True),
                 ("alert_before_minutes", 30), ("alert_grace_minutes", 10)):
        f.setdefault(k, v)

    n = cfg.setdefault("news", {})
    for k, v in (("enabled", True), ("max_age_hours", 30), ("min_score", 2),
                 ("max_items_per_feed", 12), ("max_total", 18)):
        n.setdefault(k, v)

    b = cfg.setdefault("briefing", {})
    for k, v in (("enabled", True), ("times_utc", ["06:30"]), ("horizon_hours", 24),
                 ("catchup_window_minutes", 90)):
        b.setdefault(k, v)
    if not isinstance(b["times_utc"], list):
        b["times_utc"] = [str(b["times_utc"])]

    # ── مرحله ۴: ژورنال و آمار دقت ─────────────────────────────
    j = cfg.setdefault("journal", {})
    for k, v in (("enabled", True), ("expiry_hours", 48),
                 ("conservative_both_touch", True)):
        j.setdefault(k, v)
    jn = j.setdefault("nightly", {})
    for k, v in (("enabled", True), ("time_utc", "21:30"),
                 ("catchup_window_minutes", 60)):
        jn.setdefault(k, v)
    jw = j.setdefault("weekly", {})
    for k, v in (("enabled", True), ("day_utc", 6), ("time_utc", "20:00"),
                 ("catchup_window_minutes", 120)):
        jw.setdefault(k, v)

    # ── رابط کاربری ─────────────────────────────────────────────
    u = cfg.setdefault("ui", {})
    for k, v in (("user_name", "سوشیان"), ("splash", True), ("animations", True)):
        u.setdefault(k, v)

    # ── مرحله ۳: داور امتیازدهی ────────────────────────────────
    # مقادیر پیش‌فرض در خود ماژول داور نگه داشته می‌شوند تا دو جا تکرار نشوند
    # (ایمپورت محلی: config.py نباید در سطح ماژول به judge وابسته شود)
    from .judge.scoring import judge_config
    cfg["judge"] = judge_config(cfg)

    return cfg


def save_local_config(updates: dict) -> None:
    """ذخیره تنظیمات محلی (مثل توکن تلگرام) در config.local.yaml — خارج از گیت."""
    lp = app_paths.local_config_path()
    data: dict = {}
    if lp.exists():
        try:
            with open(lp, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}
    _deep_merge(data, updates)
    with open(lp, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
