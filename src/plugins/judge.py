# -*- coding: utf-8 -*-
"""پلاگین‌های داور و سشن (فاز ۲).

⚠️ در این فاز judge-core «یکجا» ثبت می‌شود (engine + risk). شکافتن ۷ وتو
و ۸ شاهد به rule-pluginهای جدا (odin.judge.veto@1 / odin.judge.evidence@1)
کارِ فاز ۴ است — با تست parity کامل، چون حساس‌ترین بخش محاسباتی پروژه است.

قاعدهٔ adapter: فقط delegation؛ منطق در src/judge/* دست‌نخورده است.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.manifest import PluginManifest


class JudgePlugin:
    """داور + ماشین‌حساب ریسک — هر دو قرارداد را ساختاراً ارضا می‌کند."""

    def judge_config(self, cfg: dict) -> dict:
        from ..judge.scoring import judge_config
        return judge_config(cfg)

    def judge_all(self, analyses: List[Any], datasets: Dict[str, Any],
                  ctx: Any) -> List[Any]:
        from ..judge.scoring import judge_all
        return judge_all(analyses, datasets, ctx)

    def compute_levels(self, direction: str, entry: float, atr: float,
                       support: Optional[float], resistance: Optional[float],
                       rcfg: dict) -> tuple:
        from ..judge.scoring import compute_levels
        return compute_levels(direction, entry, atr, support, resistance, rcfg)


class SessionPlugin:
    def market_status(self, now: Any) -> Any:
        from ..judge.session import market_status
        return market_status(now)


def plugins() -> List[Tuple[PluginManifest, Any]]:
    return [
        (PluginManifest(
            id="session", version="1.0.0",
            provides=["odin.session@1"],
            platforms=["desktop", "android"],
            stage="judge", priority=10, optional=True),
         lambda _ctx: SessionPlugin()),
        (PluginManifest(
            id="judge-core", version="1.0.0",
            provides=["odin.judge.engine@1", "odin.judge.risk@1"],
            config={"section": "judge", "enabled_key": "enabled", "default": True},
            platforms=["desktop", "android"],
            stage="judge", priority=50, optional=True),
         lambda _ctx: JudgePlugin()),
    ]
