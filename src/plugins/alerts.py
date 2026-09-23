# -*- coding: utf-8 -*-
"""پلاگین هشدارهای قیمت (فاز ۲).

قاعدهٔ adapter: فقط delegation؛ منطق در src/alerts.py دست‌نخورده است
(همزاد js/alerts.js اندروید — یک‌بارمصرف/چسبنده/کول‌داون همان‌ها).
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from ..core.manifest import PluginManifest


class PriceAlertsPlugin:
    def check_alerts(self, analyses: List[Any], now: Optional[Any] = None) -> List[dict]:
        from .. import alerts as alerts_mod
        return alerts_mod.check_alerts(analyses, now=now)


def plugins() -> List[Tuple[PluginManifest, Any]]:
    return [
        (PluginManifest(
            id="alerts-price", version="1.0.0",
            provides=["odin.alerts.price@1"],
            # کلید فعال/غیرفعال ندارد — امروز هم همیشه فعال است (رفتار محفوظ)
            config=None,
            platforms=["desktop", "android"],
            stage="price_alerts", priority=10, optional=True),
         lambda _ctx: PriceAlertsPlugin()),
    ]
