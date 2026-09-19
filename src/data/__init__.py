# -*- coding: utf-8 -*-
"""کارخانه انتخاب منبع داده بر اساس config.yaml."""
from __future__ import annotations

from .base import DataSource, MarketData  # noqa: F401 (برای import راحت‌تر)


def get_source(cfg: dict) -> DataSource:
    kind = str(cfg.get("data_source", "yahoo")).lower()
    if kind == "mt5":
        from .mt5_source import MT5Source
        return MT5Source(cfg)
    if kind == "yahoo":
        from .yahoo_source import YahooSource
        return YahooSource(cfg)
    raise ValueError(f"منبع داده ناشناخته: {kind!r} (مقادیر مجاز: mt5 | yahoo)")
