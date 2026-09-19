# -*- coding: utf-8 -*-
"""رابط مشترک منابع داده.

هر منبع داده باید سه قاب‌داده (DataFrame) با ستون‌های
Open/High/Low/Close و ایندکس زمانی (UTC، بدون timezone) برگرداند:
M15، H1 و H4.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class MarketData:
    """داده کندل یک نماد در سه تایم‌فریم."""
    symbol: str
    m15: pd.DataFrame
    h1: pd.DataFrame
    h4: pd.DataFrame


class DataSource(ABC):
    """رابط منبع داده (MT5، Yahoo و ...)."""

    name: str = "base"

    @abstractmethod
    def connect(self) -> None:
        """اتصال به منبع داده. در صورت شکست، استثنا با پیام فارسی پرتاب کند."""

    @abstractmethod
    def disconnect(self) -> None:
        """قطع اتصال (باید بی‌خطر و قابل فراخوانی چندباره باشد)."""

    @abstractmethod
    def fetch(self, sym_cfg: dict) -> MarketData | None:
        """گرفتن داده یک نماد. در صورت نبود داده، None برگردان."""
