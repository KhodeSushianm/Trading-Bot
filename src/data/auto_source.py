# -*- coding: utf-8 -*-
"""حالت خودکار: برای هر نماد، منابع را به ترتیب اولویت امتحان می‌کند.

ترتیب: Yahoo Finance (بدون کلید) ← Twelve Data (فقط اگر کلید رایگان داشته باشد).
اگر Yahoo برای نمادی شکست بخورد و کلید TD موجود باشد، زاپاس وارد عمل می‌شود.
"""
from __future__ import annotations

from .base import DataSource, MarketData
from .yahoo_source import YahooSource


class AutoSource(DataSource):
    name = "auto"

    def __init__(self, cfg: dict):
        self.sources: list[DataSource] = [YahooSource(cfg)]
        key = str((cfg.get("twelvedata") or {}).get("api_key") or "").strip()
        if key:
            from .twelvedata_source import TwelveDataSource
            self.sources.append(TwelveDataSource(cfg))
        self._connected: list[DataSource] = []

    def connect(self) -> None:
        errors = []
        for s in self.sources:
            try:
                s.connect()
                self._connected.append(s)
            except Exception as e:
                errors.append(f"{s.name}: {e}")
        if not self._connected:
            raise RuntimeError("هیچ منبع داده‌ای متصل نشد:\n" + "\n".join(errors))
        names = " + ".join(s.name for s in self._connected)
        print(f"[auto] منابع داده فعال: {names}")

    def disconnect(self) -> None:
        for s in self.sources:
            try:
                s.disconnect()
            except Exception:
                pass

    def fetch(self, sym_cfg: dict) -> MarketData | None:
        for i, s in enumerate(self._connected):
            md = s.fetch(sym_cfg)
            if md is not None:
                if i > 0:
                    print(f"[auto] {sym_cfg['name']} از زاپاس ({s.name}) دریافت شد")
                return md
        return None
