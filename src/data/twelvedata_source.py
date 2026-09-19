# -*- coding: utf-8 -*-
"""منبع داده Twelve Data — زاپاس اختیاری (نیاز به کلید API رایگان).

ثبت‌نام: https://twelvedata.com  (فقط ایمیل لازم است)
tier رایگان: ۸۰۰ درخواست در روز، ۸ درخواست در دقیقه.
مزیت‌ها: طلای اسپات واقعی (XAU/USD) + جایگزین Yahoo وقتی در دسترس نیست.

اگر کلید در config.yaml خالی باشد، این منبع به‌صورت خودکار غیرفعال می‌شود
(در حالت auto فقط Yahoo استفاده می‌شود).
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from .base import DataSource, MarketData


class TwelveDataSource(DataSource):
    name = "twelvedata"
    BASE_URL = "https://api.twelvedata.com/time_series"

    def __init__(self, cfg: dict):
        td = cfg.get("twelvedata") or {}
        h = cfg.get("history") or {}
        self.key = str(td.get("api_key") or "").strip()
        self.min_gap = float(td.get("min_request_gap_sec", 8))
        self.drop_forming = bool(h.get("drop_forming_candle", True))
        self.sizes = {
            "15min": int(h.get("td_m15_bars", 200)),
            "1h": int(h.get("td_h1_bars", 300)),
            "4h": int(h.get("td_h4_bars", 400)),
        }
        self._last_call = 0.0

    def connect(self) -> None:
        if not self.key:
            raise RuntimeError(
                "کلید Twelve Data خالی است — کلید رایگان را از twelvedata.com بگیرید و در "
                "config.yaml (بخش twelvedata.api_key) بگذارید، یا data_source را yahoo بگذارید"
            )

    def disconnect(self) -> None:
        pass

    # ── دریافت داده ───────────────────────────────────────────
    def fetch(self, sym_cfg: dict) -> MarketData | None:
        td_sym = sym_cfg.get("td")
        if not td_sym:
            return None
        try:
            m15 = self._series(td_sym, "15min")
            h1 = self._series(td_sym, "1h")
            h4 = self._series(td_sym, "4h")
        except Exception as e:
            print(f"[!] خطای Twelve Data برای {sym_cfg['name']}: {str(e)[:140]}")
            return None
        if m15 is None or h1 is None or h4 is None:
            return None
        if len(h1) < 250 or len(h4) < 210:
            print(f"[!] تاریخچه Twelve Data برای {sym_cfg['name']} کافی نیست "
                  f"(h1={len(h1)}, h4={len(h4)})")
            return None
        return MarketData(symbol=sym_cfg["name"], m15=m15, h1=h1, h4=h4)

    # ── داخلی ─────────────────────────────────────────────────
    def _series(self, td_sym: str, interval: str) -> pd.DataFrame | None:
        # رعایت محدودیت نرخ (۸ درخواست در دقیقه در tier رایگان)
        wait = self.min_gap - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

        r = requests.get(self.BASE_URL, params={
            "symbol": td_sym, "interval": interval,
            "outputsize": self.sizes[interval], "apikey": self.key,
        }, timeout=20)
        d = r.json()
        if "values" not in d:
            raise RuntimeError(d.get("message") or d.get("status") or f"پاسخ نامعتبر (HTTP {r.status_code})")

        df = pd.DataFrame(list(reversed(d["values"])))  # API جدیدترین را اول می‌دهد
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")[["open", "high", "low", "close"]].astype(float)
        df.columns = ["Open", "High", "Low", "Close"]
        df = df.dropna()
        # قرارداد پایه: ایندکس UTC و naive (مثل Yahoo). اگر TD منطقهٔ زمانی
        # برگرداند، تبدیل می‌کنیم؛ اگر naive بود همان UTC فرض می‌شود.
        if getattr(df.index, "tz", None) is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)
        if self.drop_forming and len(df) > 1:
            df = df.iloc[:-1]
        return df
