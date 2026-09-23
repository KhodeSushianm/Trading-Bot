# -*- coding: utf-8 -*-
"""پلاگین‌های تحلیل — تکنیکال و قدرت ارزها (فاز ۲).

قاعدهٔ adapter: فقط delegation؛ منطق در src/analysis/* دست‌نخورده است.
import تنبل: ثبت پلاگین نباید pandas/ماژول‌های سنگین را در زمان import بکشد.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..core.manifest import PluginManifest


class TechnicalPlugin:
    def analyze_symbol(self, sym_cfg: dict, md: Any, acfg: dict) -> Any:
        from ..analysis.technical import analyze_symbol
        return analyze_symbol(sym_cfg, md, acfg)


class StrengthPlugin:
    def currency_strength(self, datasets: Dict[str, Any], lookback_h1: int = 24) -> List[Any]:
        from ..analysis.strength import currency_strength
        return currency_strength(datasets, lookback_h1=lookback_h1)


def plugins() -> List[Tuple[PluginManifest, Any]]:
    return [
        (PluginManifest(
            id="analysis-technical", version="1.0.0",
            provides=["odin.analysis.technical@1"],
            platforms=["desktop", "android"],
            stage="collect_market", priority=50, optional=True),
         lambda _ctx: TechnicalPlugin()),
        (PluginManifest(
            id="analysis-strength", version="1.0.0",
            provides=["odin.analysis.strength@1"],
            platforms=["desktop", "android"],
            stage="collect_market", priority=60, optional=True),
         lambda _ctx: StrengthPlugin()),
    ]
