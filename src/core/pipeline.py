# -*- coding: utf-8 -*-
"""Pipeline Runner — مراحل نام‌دار چرخه با ترتیب قطعیِ فعلی (فاز ۱).

⚠️ این اسکلت در فاز ۱ به engine وصل نیست؛ در فاز ۳ همان ترتیبِ
مو‌به‌موی run_cycle امروز را اجرا می‌کند. ترتیب مراحل عمداً از کد فعلی
(v0.24.0) رونویسی شده — از جمله این نکات رفتاری که باید حفظ شوند:
  • journal_pre *قبل* از بررسی موفقیت داده اجرا می‌شود (اگر منبع داده قطع
    باشد هم سیگنال‌های باز باید منقضی/بسته شوند).
  • بعد از journal_pre امکان «خروج زودهنگام» هست (هیچ analysis → errors).
  • بقیهٔ مراحل به همان ترتیب: فاندامنتال → وتو → داور → رندر →
    ارسال سیگنال/ژورنال → هشدار قیمت → کش نمودار → داشبورد → آرشیو/تلگرام.

سیاست خطا (codification رفتار فعلی): هندلر مرحله اگر استثنا بدهد،
StageResult با unavailable=True ثبت می‌شود، رویداد plugin.failed منتشر
می‌شود و pipeline ادامه می‌یابد — هرگز دادهٔ جعلی تولید نمی‌شود.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .bus import EventBus, Events
from .lifecycle import PluginFailure
from .registry import PluginRegistry

# مراحل چرخهٔ تحلیل — نام‌ها در مانیفست‌ها (manifest.stage) استفاده می‌شوند.
# ترتیب، رونویسِ مو‌به‌موی run_cycle فعلی است — از جمله اینکه تقویم/خبر
# *بعد* از journal_pre و امکان خروج زودهنگام دریافت می‌شوند (اگر داده قطع
# باشد، فاندامنتال هرگز واکشی نمی‌شود — همان رفتار امروز).
STAGES: tuple = (
    "collect_market",       # دادهٔ کندل + تحلیل + قدرت ارز + تاییدیهٔ TV
    "journal_pre",          # بستن سیگنال‌های باز + آمار — عمداً قبل از بررسی داده
    "collect_fundamental",  # تقویم اقتصادی + اخبار — بعد از early-exit
    "compute_vetoes",       # وتوهای نماد-محور تقویم
    "judge",                # داور: ۷ وتو + ۸ شاهد + ریسک
    "render",               # رندر گزارش‌ها (console/signal/summary)
    "dispatch_signals",     # ضداسپم → تلگرام → ثبت ژورنال
    "price_alerts",         # هشدارهای قیمت
    "chart_cache",          # کش نمودار (chart_<SYM>.json / chart.<SYM>)
    "dashboard",            # دادهٔ ساختاریافتهٔ داشبورد
    "archive_notify",       # آرشیو گزارش + ارسال تلگرام نهایی
)

# مراحل زمان‌بند (BotLoop / svcTick) — خارج از چرخهٔ تحلیل
SCHEDULER_STAGES: tuple = (
    "event_alerts",         # check_event_alerts
    "briefing",             # run_briefing
    "journal_report",       # nightly/weekly
)


@dataclass
class StageResult:
    """نتیجهٔ یک مرحله."""

    stage: str
    ok: bool = True
    value: Any = None            # خروجی هندلر/پلاگین
    unavailable: bool = False    # خطا → داده در دسترس نیست (صادقانه)
    error: str = ""
    stop: bool = False           # خروج زودهنگامِ کل pipeline (مثل early-return امروز)


@dataclass
class PipelineResult:
    ok: bool = True
    stopped_at: Optional[str] = None
    stages: List[StageResult] = field(default_factory=list)
    context: Any = None          # dict مشترک بین مراحل — در فاز ۳ = CycleContext

    def stage(self, name: str) -> Optional[StageResult]:
        for s in self.stages:
            if s.stage == name:
                return s
        return None


HandlerFn = Callable[[Any], Any]


class PipelineRunner:
    """اجرای مراحل به ترتیب + ایزولاسیون خطا + رویدادهای bus.

    دو منبع هندلر (هر دو پشتیبانی می‌شوند تا فاز ۳ انعطاف داشته باشد):
      ۱) هندلرهای صریح: add(stage, fn, priority) — fn(ctx) → value
         (value می‌تواند StageResult باشد برای stop/unavailable صریح)
      ۲) پلاگین‌های registry با manifest.stage == stage و هوک run(ctx)
         روی نمونهٔ STARTED — به ترتیب (priority، ثبت).

    ctx یک dict مشترک است؛ قراردادِ کلیدهایش در فاز ۳ فریز می‌شود.
    """

    def __init__(self, registry: Optional[PluginRegistry] = None,
                 bus: Optional[EventBus] = None,
                 log: Optional[Callable[[str], None]] = None,
                 stages: tuple = STAGES):
        self.registry = registry
        self.bus = bus or EventBus()
        self.log = log or (lambda _m: None)
        self.stages = tuple(stages)
        self._handlers: Dict[str, List[tuple]] = {s: [] for s in self.stages}

    def add(self, stage: str, fn: HandlerFn, priority: int = 100) -> None:
        if stage not in self._handlers:
            raise ValueError(f"مرحلهٔ ناشناخته «{stage}» — مراحل معتبر: {', '.join(self.stages)}")
        self._handlers[stage].append((priority, len(self._handlers[stage]), fn))

    # ── اجرا ────────────────────────────────────────────────────
    def run(self, ctx: Any, stages: Optional[List[str]] = None) -> PipelineResult:
        res = PipelineResult(context=ctx)
        for stage in (stages or list(self.stages)):
            sr = self._run_stage(stage, ctx)
            res.stages.append(sr)
            if sr.stop:
                res.stopped_at = stage
                break
            if not sr.ok:
                res.ok = False
        return res

    def _run_stage(self, stage: str, ctx: Any) -> StageResult:
        self.bus.emit(Events.STAGE_START, {"stage": stage})
        out = StageResult(stage=stage)

        # هندلرهای صریح + پلاگین‌های مرحله، هر دو به ترتیب قطعی
        chain: List[tuple] = sorted(self._handlers.get(stage, []))
        if self.registry is not None:
            for i, rec in enumerate(self.registry.by_stage(stage)):
                hook = getattr(rec.instance, "run", None) if rec.instance else None
                if callable(hook) and rec.state.value == "started":
                    chain.append((rec.manifest.priority, 1000 + i, hook))

        try:
            for _prio, _ord, fn in chain:
                value = fn(ctx)
                if isinstance(value, StageResult):     # کنترل صریح stop/unavailable
                    if value.stop:
                        out.stop = True
                        out.value = value.value
                        break
                    if value.unavailable:
                        out.unavailable = True
                        out.error = value.error
                        out.value = value.value
                        break
                    out.value = value.value
                else:
                    out.value = value
        except Exception as e:                          # noqa: BLE001 — قرنطینهٔ مرحله
            out.ok = False
            out.unavailable = True
            out.error = str(e)
            failure = PluginFailure(plugin_id=f"stage:{stage}", phase="run", error=str(e))
            self.log(failure.fa_message())
            self.bus.emit(Events.PLUGIN_FAILED, failure)

        self.bus.emit(Events.STAGE_DONE, {"stage": stage, "ok": out.ok,
                                          "unavailable": out.unavailable,
                                          "stop": out.stop})
        return out
