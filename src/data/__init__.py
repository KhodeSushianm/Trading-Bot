# -*- coding: utf-8 -*-
"""کارخانه انتخاب منبع داده بر اساس config.yaml.

منابع پشتیبانی‌شده (نسخه وب — بدون وابستگی به متاتریدر):
  auto | yahoo | twelvedata
"""
from __future__ import annotations

from .base import DataSource, MarketData  # noqa: F401 (برای import راحت‌تر)


def get_source(cfg: dict) -> DataSource:
    kind = str(cfg.get("data_source", "auto")).lower()
    if kind == "yahoo":
        from .yahoo_source import YahooSource
        return YahooSource(cfg)
    if kind == "twelvedata":
        from .twelvedata_source import TwelveDataSource
        return TwelveDataSource(cfg)
    if kind == "auto":
        from .auto_source import AutoSource
        return AutoSource(cfg)
    if kind == "mt5":
        raise ValueError(
            "منبع MT5 در این نسخه حذف شده است — پروژه به متاتریدر وابسته نیست. "
            "مقادیر مجاز: auto | yahoo | twelvedata"
        )
    raise ValueError(f"منبع داده ناشناخته: {kind!r} (مقادیر مجاز: auto | yahoo | twelvedata)")
