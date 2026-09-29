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

from .store import LEGACY_RULES_VERSION, JOURNAL_RULES_VERSION, Entry  # noqa: F401


@dataclass
class Bucket:
    closed: int = 0
    wins: int = 0
    losses: int = 0
    expired: int = 0
    r_sum: float = 0.0
    # v0.29 (فاز ۳): جمعِ Rِ *خالص* و شمارِ رکوردهایی که واقعاً هزینه
    # دارند. `net_closed` جدا از `closed` است چون رکوردهای قدیمی
    # spread_pips ندارند و net_r‌شان عیناً r است — قاطی‌کردنِ این دو یعنی
    # میانگینِ بی‌معنی. صادقانه: فقط آن‌هایی که هزینه‌شان مدل شده شمرده
    # می‌شوند.
    net_r_sum: float = 0.0
    net_closed: int = 0

    @property
    def hit_rate(self) -> Optional[float]:
        d = self.wins + self.losses
        return (self.wins / d) if d else None

    @property
    def closed_win_rate(self) -> Optional[float]:
        return (self.wins / self.closed) if self.closed else None

    @property
    def avg_r(self) -> Optional[float]:
        """میانگین Rِ *ناخالص* — برای پیوستگیِ تاریخچه (همان عددِ پیش از v0.29)."""
        return (self.r_sum / self.closed) if self.closed else None

    @property
    def avg_net_r(self) -> Optional[float]:
        """میانگین Rِ *خالصِ* پس‌از‌هزینه (v0.29).

        None یعنی «هیچ رکوردِ هزینه‌داری در این سطل نیست» — عمداً صفر
        برنمی‌گردانیم، چون صفر یک ادعایِ گمراه‌کننده است (یعنی سربه‌سر).
        """
        return (self.net_r_sum / self.net_closed) if self.net_closed else None

    def add(self, e: Entry) -> None:
        self.closed += 1
        if e.is_win:
            self.wins += 1
        elif e.is_loss:
            self.losses += 1
        else:
            self.expired += 1
        self.r_sum += (e.r or 0.0)
        # فقط رکوردهایی که هزینه‌شان *واقعاً* مدل شده، در میانگینِ خالص
        # می‌آیند. net_r == r یعنی spread_pips صفر بوده → مدل نشده.
        nr = getattr(e, "net_r", None)
        sp = float(getattr(e, "spread_pips", 0.0) or 0.0)
        if nr is not None and sp > 0.0:
            self.net_r_sum += nr
            self.net_closed += 1


@dataclass
class Excursions:
    """آمارِ نوسانِ درون‌معامله‌ای (v0.29 فاز ۴).

    چرا این کلاس وجود دارد: تا پیش از این، ژورنال فقط می‌گفت «هدف خورد» یا
    «حد ضرر». ولی پرسش‌های واقعیِ تنظیمِ خروج — «هدفِ ۲R زیادی دور بود؟»
    «سر‌به‌سر در ۱R چند باخت را نجات می‌داد؟» «برنده‌ها چقدر حرارت دیدند؟»
    — بدونِ دانستنِ اینکه قیمت *در میانهٔ معامله* تا کجا رفت، پاسخ ندارند.
    این کلاس همان داده را جمع می‌کند.

    ⚠️ همبستگی ≠ علیت: «سر‌به‌سر در ۱R این باخت‌ها را نجات می‌داد» یک
    گزارهٔ *بازخوانیِ گذشته* است. معامله‌ای که به ۱R رسیده و برگشته، با
    استاپِ سر‌به‌سر صفر می‌شد — ولی همان قاعده، معامله‌های دیگری را که
    در ۱R استاپ خورده و بعد به هدف رسیده‌اند هم می‌کُشد. این عدد فقط
    «نیمی از معادله» است و باید کنارِ ``winners_touched`` خوانده شود.
    """

    n: int = 0                       # شمارِ رکوردهای دارای MFE/MAE
    mfe_sum: float = 0.0
    mae_sum: float = 0.0
    mfe_values: list = field(default_factory=list)   # برای میانه
    mae_values: list = field(default_factory=list)
    # بازخوانیِ دو قاعدهٔ خروجِ محتمل:
    losers_reached_1r: int = 0       # باخت‌هایی که اول به ۱R+ رسیده بودند
    losers: int = 0                  # کلِ باخت‌های دارای MFE
    winners_dipped_1r: int = 0       # بردهایی که وسطِ راه ۱R علیه‌شان رفت
    winners: int = 0                 # کلِ بردهای دارای MFE

    def add(self, mfe: float, mae: float, is_win: bool, is_loss: bool) -> None:
        self.n += 1
        self.mfe_sum += mfe
        self.mae_sum += mae
        self.mfe_values.append(mfe)
        self.mae_values.append(mae)
        if is_loss:
            self.losers += 1
            if mfe >= 1.0:
                self.losers_reached_1r += 1
        elif is_win:
            self.winners += 1
            if mae <= -1.0:
                self.winners_dipped_1r += 1

    @staticmethod
    def _median(vals: list) -> Optional[float]:
        if not vals:
            return None
        v = sorted(vals)
        n = len(v)
        m = n // 2
        return v[m] if n % 2 else (v[m - 1] + v[m]) / 2.0

    @property
    def median_mfe(self) -> Optional[float]:
        return self._median(self.mfe_values)

    @property
    def median_mae(self) -> Optional[float]:
        return self._median(self.mae_values)

    @property
    def avg_mfe(self) -> Optional[float]:
        return (self.mfe_sum / self.n) if self.n else None

    @property
    def avg_mae(self) -> Optional[float]:
        return (self.mae_sum / self.n) if self.n else None

    @property
    def losers_reached_1r_rate(self) -> Optional[float]:
        """سهمِ باخت‌هایی که اول به ۱R+ رسیده بودند (نامزدِ سر‌به‌سر)."""
        return (self.losers_reached_1r / self.losers) if self.losers else None

    @property
    def winners_dipped_1r_rate(self) -> Optional[float]:
        """سهمِ بردهایی که وسطِ راه ۱R علیه‌شان رفت (بهایِ سر‌به‌سر).

        این نیمهٔ دیگرِ معادله است: سر‌به‌سر در ۱R همین‌ها را هم می‌کُشد.
        بدونِ این عدد، ``losers_reached_1r_rate`` به‌تنهایی گمراه‌کننده است.
        """
        return (self.winners_dipped_1r / self.winners) if self.winners else None


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
    # v0.29 (فاز ۴): تفکیک بر پایهٔ **نسخهٔ قواعدِ اندازه‌گیری**.
    # رکوردهای پیش از v0.29 (کلید 1) زیرِ بایاسِ «ورودِ کهنه» سنجیده شده‌اند
    # و هرگز نباید با رکوردهای v0.29 (کلید 2) در یک میانگین قاطی شوند.
    by_rules: dict[int, Bucket] = field(default_factory=dict)
    # v0.29 (فاز ۴): آمارِ نوسانِ درون‌معامله‌ای (MFE/MAE) — فقط روی
    # رکوردهایی که واقعاً این داده را دارند.
    excursions: "Excursions" = field(default_factory=lambda: Excursions())

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
        """میانگین R به ازای هر سیگنال بسته‌شده (عدد کلیدی سودمندی).

        ⚠️ این عدد *ناخالص* است — همان تعریفِ پیش از v0.29، تا تاریخچه
        قابلِ مقایسه بماند. برای تصمیم‌گیری ``expectancy_net`` را ببینید.
        """
        return self.overall.avg_r

    @property
    def expectancy_net(self) -> Optional[float]:
        """میانگین Rِ خالصِ پس‌از‌هزینه (v0.29) — عددِ درست برای تصمیم.

        None = هنوز رکوردِ هزینه‌داری نداریم (صادقانه، نه صفر).
        """
        return self.overall.avg_net_r


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
        st.by_rules.setdefault(e.rules, Bucket()).add(e)
        # نوسانِ درون‌معامله‌ای — فقط رکوردهایی که *واقعاً* داده دارند.
        # None (رکوردهای قدیمی) شمرده نمی‌شود؛ میانگینِ روی مجموعهٔ ناهمگن
        # عددِ بی‌معنی می‌داد.
        mfe, mae = getattr(e, "mfe_r", None), getattr(e, "mae_r", None)
        if mfe is not None and mae is not None:
            st.excursions.add(mfe, mae, e.is_win, e.is_loss)
    return st
