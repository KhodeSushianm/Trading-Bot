# -*- coding: utf-8 -*-
"""پلاگین‌های داده — Yahoo / TwelveData / Auto / TradingView (فاز ۲).

قاعدهٔ adapter: فقط delegation — هیچ منطق جدیدی اینجا اضافه نمی‌شود.
منطق واقعی در همان ماژول‌های فعلی (src/data/*) دست‌نخورده باقی است.

⚠️ چرا import تنبل (داخل factory/متد)؟ چون yahoo_source در سطح ماژول
`yfinance` را import می‌کند که در CI عمداً نصب نیست (خودآزمون‌ها به آن
نیاز ندارند). ثبت پلاگین باید بدون کشیدن وابستگی‌های سنگین ممکن باشد —
نمونه‌ها lazy در initialize ساخته می‌شوند (مثل امروز که get_source در زمان
نیاز صدا زده می‌شود).
"""
from __future__ import annotations

from typing import Any, List, Tuple

from ..core.manifest import PluginManifest


# ── factoryها: کلاس‌های موجود مستقیماً قرارداد odin.data.market@1 را ارضا
#    می‌کنند (connect/disconnect/fetch/name) — پس wrapper لازم ندارند.
def _yahoo(ctx: dict) -> Any:
    from ..data.yahoo_source import YahooSource
    return YahooSource(ctx["cfg"])


def _twelvedata(ctx: dict) -> Any:
    from ..data.twelvedata_source import TwelveDataSource
    return TwelveDataSource(ctx["cfg"])


def _auto(ctx: dict) -> Any:
    from ..data.auto_source import AutoSource
    return AutoSource(ctx["cfg"])


class TvPlugin:
    """adapter تریدینگ‌ویو — متد همنام با قرارداد، delegate به تابع موجود."""

    def fetch_tv_snapshot(self, symbols_cfg: List[dict], timeframe: str = "4h",
                          timeout: int = 8) -> dict:
        from ..data.tradingview import fetch_tv_snapshot
        return fetch_tv_snapshot(symbols_cfg, timeframe=timeframe, timeout=timeout)


def _tv(_ctx: dict) -> TvPlugin:
    return TvPlugin()


# انتخاب منبع داده با کلید data_source — همان معنای get_source امروز.
_KIND_TO_ID = {"auto": "data-auto", "yahoo": "data-yahoo", "twelvedata": "data-twelvedata"}


def select_market_provider(registry: Any, cfg: dict) -> Any:
    """معادل پلاگینیِ `src.data.get_source` — رکورد پلاگین منبع داده را می‌دهد.

    ⚠️ پیام‌های خطا عمداً بایت‌به‌بایت با get_source یکی‌اند (تست طلایی در
    tests/test_plugins.py همین را می‌سنجد) تا سوییچ فاز ۳ رفتار را عوض نکند.
    """
    kind = str(cfg.get("data_source", "auto")).lower()
    if kind == "mt5":
        raise ValueError(
            "منبع MT5 در این نسخه حذف شده است — پروژه به متاتریدر وابسته نیست. "
            "مقادیر مجاز: auto | yahoo | twelvedata"
        )
    pid = _KIND_TO_ID.get(kind)
    if pid is None:
        raise ValueError(
            f"منبع داده ناشناخته: {kind!r} (مقادیر مجاز: auto | yahoo | twelvedata)")
    rec = registry.by_id(pid)
    if rec is None or not rec.active:
        raise ValueError(
            f"پلاگین منبع داده «{pid}» ثبت یا فعال نیست — data_source: {kind}")
    return rec


def plugins() -> List[Tuple[PluginManifest, Any]]:
    return [
        (PluginManifest(
            id="data-auto", version="1.0.0",
            provides=["odin.data.market@1"],
            platforms=["desktop"], stage="collect_market", priority=10,
            optional=True), _auto),
        (PluginManifest(
            id="data-yahoo", version="1.0.0",
            provides=["odin.data.market@1"],
            platforms=["desktop"], stage="collect_market", priority=20,
            optional=True), _yahoo),
        (PluginManifest(
            id="data-twelvedata", version="1.0.0",
            provides=["odin.data.market@1"],
            platforms=["desktop"], stage="collect_market", priority=30,
            optional=True), _twelvedata),
        (PluginManifest(
            id="data-tradingview", version="1.0.0",
            provides=["odin.data.tv@1"],
            config={"section": "tradingview", "enabled_key": "enabled", "default": True},
            platforms=["desktop"], stage="collect_market", priority=40,
            optional=True), _tv),
    ]
