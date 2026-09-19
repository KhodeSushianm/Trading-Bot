# -*- coding: utf-8 -*-
"""منبع داده Yahoo Finance — منبع اصلی کندل‌ها (رایگان و بدون کلید).

جفت‌ارزها با پسوند "=X" (مثل EURUSD=X) و طلا با نماد فیوچرز GC=F.
در حالت auto، اگر Yahoo برای نمادی شکست بخورد و کلید Twelve Data موجود
باشد، زاپاس وارد عمل می‌شود.
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from .base import DataSource, MarketData


class YahooSource(DataSource):
    name = "yahoo"

    def __init__(self, cfg: dict):
        h = cfg.get("history", {}) or {}
        self.h1_days = str(h.get("yahoo_h1_days", 60)) and f"{h.get('yahoo_h1_days', 60)}d"
        self.m15_days = f"{h.get('yahoo_m15_days', 5)}d"
        self.drop_forming = bool(h.get("drop_forming_candle", True))

    def connect(self) -> None:
        pass  # بدون اتصال — درخواست‌های HTTP موردی

    def disconnect(self) -> None:
        pass

    # ── دریافت داده ───────────────────────────────────────────
    def fetch(self, sym_cfg: dict) -> MarketData | None:
        yahoo_sym = sym_cfg.get("yahoo") or f"{sym_cfg['name']}=X"
        h1 = self._download(yahoo_sym, "1h", self.h1_days)
        m15 = self._download(yahoo_sym, "15m", self.m15_days)
        if (h1 is None or m15 is None) and sym_cfg.get("yahoo_alt"):
            h1 = self._download(sym_cfg["yahoo_alt"], "1h", self.h1_days)
            m15 = self._download(sym_cfg["yahoo_alt"], "15m", self.m15_days)
        if h1 is None or m15 is None or len(h1) < 250:
            print(f"[!] داده Yahoo برای {sym_cfg['name']} ناقص است — رد شد")
            return None
        h4 = self._to_h4(h1)
        if h4 is None or len(h4) < 210:
            print(f"[!] داده H4 (بازنمونه‌شده) برای {sym_cfg['name']} کافی نیست — رد شد")
            return None
        return MarketData(symbol=sym_cfg["name"], m15=m15, h1=h1, h4=h4)

    # ── داخلی ─────────────────────────────────────────────────
    def _download(self, ticker: str, interval: str, period: str) -> pd.DataFrame | None:
        try:
            df = yf.download(ticker, period=period, interval=interval,
                             progress=False, auto_adjust=True)
        except Exception as e:
            print(f"[!] خطای دانلود {ticker}: {e}")
            return None
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close"]].dropna()
        if df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)
        if self.drop_forming and len(df) > 1:
            df = df.iloc[:-1]  # آخرین کندل ممکن است هنوز بسته نشده باشد
        return df

    @staticmethod
    def _to_h4(h1: pd.DataFrame) -> pd.DataFrame:
        return (h1.resample("4h")
                  .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
                  .dropna())
