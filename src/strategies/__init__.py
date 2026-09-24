# -*- coding: utf-8 -*-
"""استراتژی‌های ورود ODIN (v0.26) — منطقِ خالص، بی‌وابسته به چارچوب.

سه استراتژی (تصویب مالک):
  • trend_pullback   — روند + پولبک + تأیید ادامه (proposes=True)
  • london_breakout  — شکست محدودهٔ آسیا در پنجرهٔ لندن (proposes=True)
  • carry            — صرفِ نرخ بهره + هم‌جهتی فاندامنتال (proposes=False)

هر سه یک امضا دارند: evaluate(a, md, scfg, ctx) → StrategyVerdict
(قرارداد odin.strategy@1). adapterهای نازک در src/plugins/strategies.py
این‌ها را در registry ثبت می‌کنند؛ مصرف‌کننده (داور) در S3 وصل می‌شود.
"""
from __future__ import annotations

from . import carry, london_breakout, trend_pullback
from .base import StrategyVerdict

__all__ = ["StrategyVerdict", "trend_pullback", "london_breakout", "carry"]
