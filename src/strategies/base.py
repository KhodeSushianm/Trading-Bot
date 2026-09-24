# -*- coding: utf-8 -*-
"""پایهٔ استراتژی‌های ورود (v0.26 — تصمیم مالک: سیگنال بر اساس استراتژی).

هر استراتژی یک تابع خالص `evaluate(a, md, scfg, ctx)` است که
`StrategyVerdict` برمی‌گرداند. قوانین سخت (معماری پلاگین):

  • خالص و قطعی: بدون I/O، بدون ساعت جهانی (زمان از ctx.now می‌آید)،
    بدون حالت داخلی — تا آینهٔ JS بایت‌به‌بایت همان خروجی را بدهد
    (fixtures پاریتی) و تست‌های طلایی قابل اتکا باشند.
  • صادقانه: نبود داده → direction="NONE" با دلیل فارسی صریح؛ هرگز
    حدس یا دادهٔ جعلی نه.
  • shape قرارداد `odin.strategy@1` (src/core/contracts.py):
      key, name_fa, direction (BUY|SELL|NONE), strength (0..1),
      proposes (bool), reasons_fa (list[str]), detail_fa (str)
    `proposes=False` یعنی استراتژی فقط در «دروازهٔ توافق» شرکت می‌کند
    (مثل carry که سوگیریِ کند است) و نمی‌تواند به‌تنهایی منبعِ جهتِ
    سیگنال باشد.

⚠️ این ماژول‌ها در S1 «برق وصل نیستند» — engine/داور هنوز مصرفشان
   نمی‌کند؛ سوییچ در S3 با بازضبطِ مستندِ میخ‌های متأثر انجام می‌شود.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional


@dataclass
class StrategyVerdict:
    """نتیجهٔ ارزیابی یک استراتژی برای یک نماد."""

    key: str                       # trend_pullback | london_breakout | carry
    name_fa: str                   # نام فارسی برای گزارش/ژورنال
    direction: str                 # BUY | SELL | NONE
    strength: float                # 0..1 — قدرت ستاپ (برای اولویت‌بندی)
    proposes: bool                 # آیا منبعِ جهتِ سیگنال است؟ (carry: False)
    reasons_fa: List[str] = field(default_factory=list)
    detail_fa: str = ""

    def to_dict(self) -> dict:
        """نگاشت قطعی (کلیدهای مرتب) — برای ژورنال، fixtures و مقایسهٔ طلایی."""
        return {"key": self.key, "name_fa": self.name_fa,
                "direction": self.direction, "strength": self.strength,
                "proposes": self.proposes, "reasons_fa": list(self.reasons_fa),
                "detail_fa": self.detail_fa}


def none(key: str, name_fa: str, reason_fa: str, proposes: bool = True) -> StrategyVerdict:
    """نتیجهٔ NONE با دلیل صادقانه — الگوی مشترک همهٔ استراتژی‌ها."""
    return StrategyVerdict(key=key, name_fa=name_fa, direction="NONE",
                           strength=0.0, proposes=proposes,
                           reasons_fa=[reason_fa],
                           detail_fa=f"{name_fa}: {reason_fa}")


def utc_of(dt: Optional[datetime]) -> Optional[datetime]:
    """نرمال‌سازی زمان به UTC: naive = UTC فرض می‌شود (قرارداد src/data/base)،
    aware = تبدیل می‌شود. هیچ‌وقت استثنا نمی‌دهد (None → None)."""
    if dt is None:
        return None
    try:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def ctx_now(ctx: Any) -> datetime:
    """زمانِ چرخه از ctx (JudgeContext.now) — نبود/خرابی → ساعت جهانی UTC.

    تنها نقطهٔ مجازِ خواندن ساعت در استراتژی‌ها؛ تست‌ها ctx.now ثابت
    تزریق می‌کنند تا رفتار قطعی بماند.
    """
    now = utc_of(getattr(ctx, "now", None)) if ctx is not None else None
    return now if now is not None else datetime.now(timezone.utc)
