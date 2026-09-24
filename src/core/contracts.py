# -*- coding: utf-8 -*-
"""قراردادهای هستهٔ پلاگین (فاز ۱ معماری Modular + Plugin-Driven).

این فایل «تنها» جایی است که هسته، شکلِ قابلیت‌ها را می‌شناسد — نه خودِ
قابلیت‌ها را. یعنی هسته هیچ‌وقت RSI، Yahoo، News یا TradingView را
نمی‌شناسد؛ فقط این Protocolها را می‌شناسد.

اصول طراحی (تصویب‌شده در Preview فاز ۱):
  ۱) shape-only: هیچ import از ماژول‌های فیچر (src/data، src/judge و ...)
     اینجا مجاز نیست. انواع بازگشتیِ خاصِ فیچرها (MarketData، SymbolAnalysis،
     Judgment و ...) عمداً Any هستند تا استقلال هسته تضمین بماند؛ شکلِ واقعی
     آن‌ها در docstring هر قرارداد مستند شده و در فاز ۲ با «تست طلایی»
     (adapter == فراخوانی مستقیم) اثبات می‌شود.
  ۲) امضاها ۱:۱ از کد فعلی (v0.24.0) مشتق شده‌اند — قرارداد جدید یعنی
     شکستن قرارداد موجود، و آن فقط با تأیید مالک ممکن است.
  ۳) نسخه‌گذاری: شناسهٔ قراردادها `name@major` است. تغییر shape سازگار
     (افزودن متد اختیاری) بدون bump؛ تغییر ناسازگار → `@2` و نگهداری
     همزمان هر دو تا مهاجرت کامل.

⚠️ این ماژول در فاز ۱ «برق وصل نیست» — فقط tests/test_core.py مصرفش
   می‌کند. اتصال واقعی در فاز ۲ (adapterها) و فاز ۳ (سوییچ engine) است.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

# الگوی شناسهٔ قرارداد: odin.<دامنه>[.<زیردامنه>]@<major>
CONTRACT_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9]+)+@\d+$")

LogFn = Callable[[str], None]


# ══════════════════════════════════════════════════════════════
#  داده
# ══════════════════════════════════════════════════════════════
@runtime_checkable
class MarketDataProvider(Protocol):
    """`odin.data.market@1` — منبع کندل (Yahoo / TwelveData / Auto).

    شکل بازگشتی fetch: دیتاکلاس `src.data.base.MarketData`
    (symbol + سه DataFrame با ستون‌های Open/High/Low/Close و ایندکس UTC).
    دقیقاً همان ABC موجود در src/data/base.py — بدون تغییر.
    """

    name: str

    def connect(self) -> None:
        """اتصال؛ در صورت شکست استثنا با پیام فارسی."""
        ...

    def disconnect(self) -> None:
        """قطع اتصال — بی‌خطر و چندبارصدازن."""
        ...

    def fetch(self, sym_cfg: dict) -> Optional[Any]:
        """دادهٔ یک نماد؛ نبود داده → None (هرگز دادهٔ جعلی نه)."""
        ...


@runtime_checkable
class TvConfirmationProvider(Protocol):
    """`odin.data.tv@1` — تاییدیهٔ تریدینگ‌ویو (shape: fetch_tv_snapshot فعلی)."""

    def fetch_tv_snapshot(self, symbols_cfg: List[dict], timeframe: str = "4h",
                          timeout: int = 8) -> Dict[str, Any]:
        """نگاشت symbol → TVSnapshot؛ خطا/نبود کتابخانه → {} (صادقانه)."""
        ...


# ══════════════════════════════════════════════════════════════
#  تحلیل
# ══════════════════════════════════════════════════════════════
@runtime_checkable
class TechnicalAnalyzer(Protocol):
    """`odin.analysis.technical@1` — shape: analyze_symbol فعلی."""

    def analyze_symbol(self, sym_cfg: dict, md: Any, acfg: dict) -> Any:
        """ورودی MarketData، خروجی SymbolAnalysis (verdict/trend/adx/rsi/...)."""
        ...


@runtime_checkable
class StrengthAnalyzer(Protocol):
    """`odin.analysis.strength@1` — shape: currency_strength فعلی."""

    def currency_strength(self, datasets: Dict[str, Any],
                          lookback_h1: int = 24) -> List[Any]:
        """ورودی نگاشت symbol→MarketData، خروجی فهرست (currency, score) مرتب."""
        ...


@runtime_checkable
class SessionStatusProvider(Protocol):
    """`odin.session@1` — shape: market_status فعلی (judge/session.py)."""

    def market_status(self, now: Any) -> Any:
        """ورودی datetime (UTC-aware)، خروجی MarketStatus (open/sessions/...)."""
        ...


# ══════════════════════════════════════════════════════════════
#  فاندامنتال
# ══════════════════════════════════════════════════════════════
@runtime_checkable
class CalendarProvider(Protocol):
    """`odin.fundamental.calendar@1` — shape: توابع عمومی calendar.py فعلی."""

    def fetch_calendar(self, cfg: Optional[dict] = None,
                       on_log: Optional[LogFn] = None,
                       use_cache: bool = True, timeout: int = 15) -> Any:
        """خروجی CalendarSnapshot (هرگز استثنا نه — snap.ok=False)."""
        ...

    def upcoming_events(self, snap: Any, now: Optional[Any] = None,
                        hours: float = 72.0,
                        impacts: tuple = ("HIGH", "MEDIUM"),
                        countries: Optional[Any] = None,
                        limit: Optional[int] = None) -> List[Any]:
        ...

    def veto_for_symbol(self, snap: Any, base: str, quote: str,
                        now: Any, minutes: float = 30.0) -> List[Any]:
        """رویدادهای پراثر نزدیک → فهرست CalendarEvent (خالی = بدون وتو)."""
        ...


@runtime_checkable
class NewsProvider(Protocol):
    """`odin.fundamental.news@1` — shape: fetch_news فعلی."""

    def fetch_news(self, cfg: Optional[dict] = None,
                   on_log: Optional[LogFn] = None,
                   max_age_hours: Optional[float] = None) -> Any:
        """خروجی NewsSnapshot (هرگز استثنا نه — snap.ok=False)."""
        ...


# ══════════════════════════════════════════════════════════════
#  داور (فاز ۴: وتوها/شاهدها به rule-plugin جدا تبدیل می‌شوند)
# ══════════════════════════════════════════════════════════════
@runtime_checkable
class JudgeEngine(Protocol):
    """`odin.judge.engine@1` — shape: judge_all/judge_config فعلی."""

    def judge_config(self, cfg: dict) -> dict:
        """ادغام پیش‌فرض‌های داور با config (منبع حقیقت: scoring.py)."""
        ...

    def judge_all(self, analyses: List[Any], datasets: Dict[str, Any],
                  ctx: Any) -> List[Any]:
        """ورودی JudgeContext، خروجی فهرست Judgment (signal یا reject_reason)."""
        ...


@runtime_checkable
class VetoRule(Protocol):
    """`odin.judge.veto@1` — یک دروازهٔ وتو (۷ قاعدهٔ فعلی collect_vetoes).

    هر قاعده یا Veto برمی‌گرداند یا None. ترتیب ارزیابی و متن‌های فارسی
    در فاز ۴ دقیقاً مثل امروز حفظ می‌شود (فقط مرزها عوض می‌شود).
    """

    veto_id: str          # DATA | WEEKEND | TF_CONFLICT | RANGE | EVENT | VOL_SPIKE | BREAKING_NEWS

    def rule(self, a: Any, sym_cfg: dict, md: Optional[Any],
             ctx: Any) -> Optional[Any]:
        ...


@runtime_checkable
class EvidenceRule(Protocol):
    """`odin.judge.evidence@1` — یک شاهد امتیاز (۸ تابع ev_* فعلی).

    ⚠️ ev_session امروز فقط (ctx) می‌گیرد؛ adapterِ آن در فاز ۴ همین
    shapeِ یکدست را با نادیده‌گرفتن a/direction فراهم می‌کند — بدون تغییر
    رفتار. ترتیب فهرست شاهدها (trend, level, fundamental, momentum,
    strength, news, tradingview, session) با priority مانیفست ثابت می‌ماند.
    """

    evidence_id: str      # TREND | LEVEL | FUNDAMENTAL | MOMENTUM | STRENGTH | NEWS | TV | SESSION

    def rule(self, a: Any, ctx: Any, direction: str) -> Any:
        """خروجی Evidence (points/max_points/title_fa/...)."""
        ...


@runtime_checkable
class RiskCalculator(Protocol):
    """`odin.judge.risk@1` — shape: compute_levels فعلی."""

    def compute_levels(self, direction: str, entry: float, atr: float,
                       support: Optional[float], resistance: Optional[float],
                       rcfg: dict) -> tuple:
        """خروجی (sl, tp, rr, capped) — ریاضی SL/TP بدون تغییر."""
        ...


@runtime_checkable
class StrategyRule(Protocol):
    """`odin.strategy@1` — استراتژی ورود (v0.26؛ تصمیم مالک).

    قراردادِ افزودنیِ تازه — اولین قراردادِ پس از مهاجرت. شکل بازگشتی
    (dataclass `src/strategies/base.py::StrategyVerdict` یا معادل dict):
      key: str            — شناسهٔ استراتژی (trend_pullback و ...)
      name_fa: str        — نام فارسی برای گزارش
      direction: str      — BUY | SELL | NONE
      strength: float     — 0..1 (قدرت ستاپ؛ برای اولویت‌بندیِ تعارض‌ها)
      proposes: bool      — آیا منبعِ جهتِ سیگنال است؟ (carry = False:
                            فقط در دروازهٔ توافق شرکت می‌کند)
      reasons_fa: list    — دلایل عددی/فارسی (قابل نمایش)
      detail_fa: str      — یک خط خلاصهٔ صادقانه

    ارزیابی باید خالص و قطعی باشد (بدون I/O؛ زمان فقط از ctx.now) تا
    آینهٔ JS (js/strategies.js) در fixtures پاریتی بایت‌به‌بایت مطابقت کند.
    """

    def evaluate(self, a: Any, md: Any, ctx: Any) -> Any:
        """a=SymbolAnalysis، md=MarketData|None، ctx=JudgeContext → StrategyVerdict."""
        ...


# ══════════════════════════════════════════════════════════════
#  ژورنال · اعلان · هشدار · گزارش
# ══════════════════════════════════════════════════════════════
@runtime_checkable
class JournalService(Protocol):
    """`odin.journal@1` — facade سه جزء فعلی (store/tracker/stats)."""

    def open(self, path: Optional[Any] = None) -> Any:
        """ساخت Journal (مسیر پیش‌فرض: logs/journal.jsonl مثل امروز)."""
        ...

    def resolve_open_signals(self, journal: Any, datasets: Dict[str, Any],
                             now: Optional[Any] = None,
                             cfg: Optional[dict] = None,
                             on_log: Optional[LogFn] = None) -> List[Any]:
        """بستن سیگنال‌های باز از روی کندل‌ها → فهرست Entry بسته‌شده."""
        ...

    def compute_stats(self, entries: List[Any], now: Any) -> Any:
        """آمار دقت (wins/losses/expired/hit_rate/avg_r) → Stats."""
        ...


@runtime_checkable
class Notifier(Protocol):
    """`odin.notify@1` — shape: _send_telegram فعلی در engine."""

    def send(self, cfg: dict, text: str, on_log: Optional[LogFn] = None,
             label: str = "گزارش") -> tuple:
        """خروجی (ok: bool, message: str) — هرگز استثنا نه."""
        ...


@runtime_checkable
class PriceAlertChecker(Protocol):
    """`odin.alerts.price@1` — shape: check_alerts فعلی (src/alerts.py)."""

    def check_alerts(self, analyses: List[Any], now: Optional[Any] = None) -> List[dict]:
        """فهرست هشدارهای فعال‌شده (dict با symbol/dir/price/_price)."""
        ...


@runtime_checkable
class ReportRenderer(Protocol):
    """`odin.report@1` — رندر نام‌دار گزارش‌ها (report/*.py فعلی).

    kindهای معتبر (فاز ۲): signal | judge_summary | no_signals_note |
    calendar | news | event_alert | briefing | stats | nightly | console |
    symbol | strength | veto | card (دسکتاپ).
    خروجی اکثر kindها str است؛ `card` عمداً Any (QPixmap — فقط دسکتاپ).
    """

    def render(self, kind: str, payload: dict) -> Any:
        ...


# ══════════════════════════════════════════════════════════════
#  ثبت مرکزی قراردادها
# ══════════════════════════════════════════════════════════════
CONTRACTS: Dict[str, type] = {
    "odin.data.market@1": MarketDataProvider,
    "odin.data.tv@1": TvConfirmationProvider,
    "odin.analysis.technical@1": TechnicalAnalyzer,
    "odin.analysis.strength@1": StrengthAnalyzer,
    "odin.session@1": SessionStatusProvider,
    "odin.fundamental.calendar@1": CalendarProvider,
    "odin.fundamental.news@1": NewsProvider,
    "odin.judge.engine@1": JudgeEngine,
    "odin.judge.veto@1": VetoRule,
    "odin.judge.evidence@1": EvidenceRule,
    "odin.judge.risk@1": RiskCalculator,
    "odin.strategy@1": StrategyRule,
    "odin.journal@1": JournalService,
    "odin.notify@1": Notifier,
    "odin.alerts.price@1": PriceAlertChecker,
    "odin.report@1": ReportRenderer,
}


def is_valid_contract_id(cid: str) -> bool:
    """شناسهٔ قرارداد باید هم خوش‌شکل باشد هم در CONTRACTS ثبت شده باشد."""
    return bool(CONTRACT_ID_RE.match(cid or "")) and cid in CONTRACTS


def is_wellformed_contract_id(cid: str) -> bool:
    """فقط شکل شناسه (برای خطاهای زودهنگامِ مانیفست — حتی اگر ناشناخته باشد)."""
    return bool(CONTRACT_ID_RE.match(cid or ""))
