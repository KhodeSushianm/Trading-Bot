# -*- coding: utf-8 -*-
"""منبع داده MetaTrader 5 — برای اجرای نهایی روی ویندوز کاربر.

پیش‌نیاز:
  1) ترمینال MT5 نصب و (ترجیحاً) باز و لاگین‌شده باشد
  2) پکیج MetaTrader5 نصب باشد:  pip install MetaTrader5
"""
from __future__ import annotations

import pandas as pd

from .base import DataSource, MarketData

try:
    import MetaTrader5 as mt5
except ImportError:  # روی سیستم‌های غیر ویندوز
    mt5 = None


class MT5Source(DataSource):
    name = "mt5"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        m5 = cfg.get("mt5", {}) or {}
        h = cfg.get("history", {}) or {}
        self.suffix: str = m5.get("symbol_suffix", "") or ""
        self.counts = {
            "h4": int(h.get("mt5_h4_bars", 400)),
            "h1": int(h.get("mt5_h1_bars", 300)),
            "m15": int(h.get("mt5_m15_bars", 200)),
        }
        self.drop_forming = bool(h.get("drop_forming_candle", True))
        self._init_kwargs = {}
        if m5.get("terminal_path"):
            self._init_kwargs["path"] = m5["terminal_path"]
        if m5.get("login"):
            self._init_kwargs.update(
                login=int(m5["login"]),
                password=str(m5.get("password", "")),
                server=str(m5.get("server", "")),
            )

    # ── اتصال ─────────────────────────────────────────────────
    def connect(self) -> None:
        if mt5 is None:
            raise RuntimeError(
                "پکیج MetaTrader5 نصب نیست. روی ویندوز اجرا کنید: pip install MetaTrader5"
            )
        if not mt5.initialize(**self._init_kwargs):
            raise RuntimeError(
                f"اتصال به MT5 ناموفق بود: {mt5.last_error()} — "
                "ترمینال MT5 باید نصب و باز باشد"
            )
        info = mt5.terminal_info()
        if info is not None and not info.connected:
            raise RuntimeError("ترمینال MT5 به سرور بروکر وصل نیست — اینترنت/لاگین را چک کنید")

    def disconnect(self) -> None:
        if mt5 is not None:
            try:
                mt5.shutdown()
            except Exception:
                pass

    # ── دریافت داده ───────────────────────────────────────────
    def fetch(self, sym_cfg: dict) -> MarketData | None:
        symbol = f"{sym_cfg['mt5']}{self.suffix}"
        if not mt5.symbol_select(symbol, True):
            # تلاش بدون پسوند (برخی بروکرها نام متفاوت دارند)
            symbol = sym_cfg["mt5"]
            if not mt5.symbol_select(symbol, True):
                print(f"[!] نماد {sym_cfg['name']} در MT5 پیدا نشد "
                      f"(نام بروکر را در Market Watch چک کنید؛ شاید نیاز به symbol_suffix دارد)")
                return None
        h4 = self._rates(symbol, mt5.TIMEFRAME_H4, self.counts["h4"])
        h1 = self._rates(symbol, mt5.TIMEFRAME_H1, self.counts["h1"])
        m15 = self._rates(symbol, mt5.TIMEFRAME_M15, self.counts["m15"])
        if h4 is None or h1 is None or m15 is None:
            return None
        return MarketData(symbol=symbol, m15=m15, h1=h1, h4=h4)

    def _rates(self, symbol: str, timeframe, count: int) -> pd.DataFrame | None:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            print(f"[!] دریافت کندل {symbol} ناموفق: {mt5.last_error()}")
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")  # زمان سرور بروکر (معمولاً UTC+2/3)
        df = df.set_index("time")[["open", "high", "low", "close"]]
        df.columns = ["Open", "High", "Low", "Close"]
        df = df.dropna()
        if self.drop_forming and len(df) > 1:
            df = df.iloc[:-1]  # کندل در حال تشکیل حذف شود
        return df
