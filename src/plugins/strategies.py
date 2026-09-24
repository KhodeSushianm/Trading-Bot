# -*- coding: utf-8 -*-
"""پلاگین‌های استراتژی (v0.26 — S1: ثبت در registry، مصرف در S3).

سه adapter نازک با قرارداد جدید `odin.strategy@1` — delegation خالص به
ماژول‌های src/strategies/* (منطق آنجاست، اینجا فقط ثبت و اتصال config):

  strategy-trend-pullback  → strategies.trend_pullback.evaluate
  strategy-london-breakout → strategies.london_breakout.evaluate
  strategy-carry           → strategies.carry.evaluate

اتصال فعال/غیرفعال: strategies.<key>.enabled (dot-path فاز ۷ در
config-bridge) — خاموش‌کردن یک استراتژی یعنی حذفش از فهرستِ توافق‌ها،
بدون دست‌زدن به بقیه. stage="judge" چون استراتژی‌ها خوراکِ داورند.

قاعدهٔ معماری: adapter هیچ منطقی ندارد؛ golden تست
(tests/test_strategies.py) برابری «مسیر registry == فراخوانی مستقیم» را
بایت‌به‌بایت پین می‌کند.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from ..core.manifest import PluginManifest

# (plugin_id, strategy_key) — ترتیب = priority ارزیابی (قطعی)
STRATEGY_RULES: List[Tuple[str, str]] = [
    ("strategy-trend-pullback", "trend_pullback"),
    ("strategy-london-breakout", "london_breakout"),
    ("strategy-carry", "carry"),
]


class StrategyAdapter:
    """adapter نازک یک استراتژی — قرارداد odin.strategy@1.

    scfg در ساخت گرفته می‌شود (context["cfg"]["strategies"][key]) — factory
    در هر _Caps با cfg جاری ساخته می‌شود، پس تغییرات config (مثل اندروید)
    بین چرخه‌ها درست دیده می‌شوند.
    """

    def __init__(self, key: str, cfg: Optional[dict] = None):
        self.key = key
        strategies = (cfg or {}).get("strategies") or {}
        self._scfg: dict = dict(strategies.get(key) or {})

    def evaluate(self, a: Any, md: Any, ctx: Any) -> Any:
        from ..strategies import carry, london_breakout, trend_pullback
        mod = {"trend_pullback": trend_pullback,
               "london_breakout": london_breakout,
               "carry": carry}[self.key]
        return mod.evaluate(a, md, self._scfg, ctx)


def plugins() -> List[Tuple[PluginManifest, Any]]:
    out: List[Tuple[PluginManifest, Any]] = []
    for i, (pid, key) in enumerate(STRATEGY_RULES):
        out.append((
            PluginManifest(
                id=pid, version="1.0.0",
                provides=["odin.strategy@1"],
                config={"section": "strategies",
                        "enabled_key": f"{key}.enabled", "default": True},
                platforms=["desktop", "android"],
                stage="judge", priority=10 * (i + 1), optional=True),
            lambda ctx, k=key: StrategyAdapter(
                k, (ctx or {}).get("cfg") if isinstance(ctx, dict) else None)))
    return out
