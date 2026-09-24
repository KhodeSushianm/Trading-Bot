# -*- coding: utf-8 -*-
"""آمار دقت ژورنال — «حلقهٔ صداقت».

چه چیزی حساب می‌شود:
  • کلی: تعداد بسته‌شده، برد/باخت/منقضی، نرخ برد، میانگین R، انتظار ریاضی
  • هفتگی (هفتهٔ ISO) + مقایسه با هفتهٔ قبل
  • به تفکیک نماد، جهت، بازهٔ امتیاز، و **مدرک** (کدام مدرک واقعاً همبسته با برد است)

تعریف نرخ برد:
  ``hit_rate``        = برد / (برد + باخت)      ← فقط نتیجه‌های قطعی
  ``decisive_rate``   = همان، ولی منقضی‌ها هم از مخرج بیرون‌اند (یکی هستند)
  ``closed_win_rate`` = برد / کل بسته‌شده       ← منقضی را «نبرد» می‌شمارد (محتاطانه)
هر سه گزارش می‌شوند تا عدد واحدی گمراه‌کننده نباشد.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .store import Entry


@dataclass
class Bucket:
    closed: int = 0
    wins: int = 0
    losses: int = 0
    expired: int = 0
    r_sum: float = 0.0

    @property
    def hit_rate(self) -> Optional[float]:
        d = self.wins + self.losses
        return (self.wins / d) if d else None

    @property
    def closed_win_rate(self) -> Optional[float]:
        return (self.wins / self.closed) if self.closed else None

    @property
    def avg_r(self) -> Optional[float]:
        return (self.r_sum / self.closed) if self.closed else None

    def add(self, e: Entry) -> None:
        self.closed += 1
        if e.is_win:
            self.wins += 1
        elif e.is_loss:
            self.losses += 1
        else:
            self.expired += 1
        self.r_sum += (e.r or 0.0)


@dataclass
class Stats:
    now: datetime
    total: int = 0
    open_count: int = 0
    overall: Bucket = field(default_factory=Bucket)
    by_week: dict[str, Bucket] = field(default_factory=dict)
    by_symbol: dict[str, Bucket] = field(default_factory=dict)
    by_direction: dict[str, Bucket] = field(default_factory=dict)
    by_score: dict[str, Bucket] = field(default_factory=dict)
    by_evidence: dict[str, Bucket] = field(default_factory=dict)
    # S4 (v0.27): سرنوشتِ سیگنال‌هایی که هر استراتژی با آن‌ها *توافق* کرد —
    # همان فلسفهٔ by_evidence (همبستگی ≠ علیت؛ صادقانه در متن کارنامه)
    by_strategy: dict[str, Bucket] = field(default_factory=dict)

    @property
    def last_week_key(self) -> Optional[str]:
        keys = sorted(self.by_week)
        if len(keys) < 2:
            return None
        return keys[-2]

    @property
    def this_week_key(self) -> Optional[str]:
        keys = sorted(self.by_week)
        return keys[-1] if keys else None

    @property
    def expectancy(self) -> Optional[float]:
        """میانگین R به ازای هر سیگنال بسته‌شده (عدد کلیدی سودمندی)."""
        return self.overall.avg_r


def _score_bucket(score: int) -> str:
    if score >= 10:
        return "۱۰–۱۱"
    if score >= 9:
        return "۹"
    if score >= 8:
        return "۸"
    return "۷"


def compute_stats(entries: list[Entry], now: datetime) -> Stats:
    st = Stats(now=now)
    st.total = len(entries)
    for e in entries:
        if e.is_open:
            st.open_count += 1
            continue
        st.overall.add(e)
        st.by_week.setdefault(e.week_key, Bucket()).add(e)
        st.by_symbol.setdefault(e.symbol, Bucket()).add(e)
        st.by_direction.setdefault(e.direction, Bucket()).add(e)
        st.by_score.setdefault(_score_bucket(e.score), Bucket()).add(e)
        for k in e.evidence_keys():
            st.by_evidence.setdefault(k, Bucket()).add(e)
        for k in e.strategies:
            st.by_strategy.setdefault(k, Bucket()).add(e)
    return st
