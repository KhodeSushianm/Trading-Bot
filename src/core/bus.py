# -*- coding: utf-8 -*-
"""Event Bus هسته — pub/sub همگام با ایزولاسیون استثنا (فاز ۱).

تصمیم‌های طراحی (تصویب‌شده در Preview فاز ۱):
  • همگام و fire-and-forget: listenerها هرگز نتیجهٔ pipeline را تغییر
    نمی‌دهند — قطعیت خروجی (و بنابراین parity با اوراکل) حفظ می‌شود.
  • هر listener در try/except مستقل: listener خراب، بقیه را نمی‌شکند و
    emit هیچ‌وقت استثنا بیرون نمی‌دهد (خطاها در خروجی برگردانده می‌شوند).
  • ترتیب اجرا = ترتیب ثبت (قطعی و قابل تست).
  • بدون threading: مثل امروز، رویدادها روی همان نخِ چرخه منتشر می‌شوند؛
    BotLoop/_publish مکانیزم UI خودش را دارد و دست‌نخورده است.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple


class Events:
    """نام رویدادهای استاندارد — همان جریان فعلی run_cycle/BotLoop، نام‌گذاری‌شده."""

    # چرخهٔ تحلیل
    CYCLE_START = "cycle.start"
    MARKET_COLLECTED = "market.collected"
    JOURNAL_RESOLVED = "journal.resolved"
    FUNDAMENTAL_COLLECTED = "fundamental.collected"
    VETOES_COMPUTED = "vetoes.computed"
    JUDGE_DONE = "judge.done"
    SIGNAL_CREATED = "signal.created"
    SIGNAL_SENT = "signal.sent"
    ALERTS_FIRED = "alerts.fired"
    REPORT_RENDERED = "report.rendered"
    TELEGRAM_SENT = "telegram.sent"
    CYCLE_END = "cycle.end"

    # رویدادهای زمان‌بند (BotLoop / svcTick)
    NEWS_BREAKING = "news.breaking"
    BRIEFING_DUE = "briefing.due"
    JOURNAL_DUE = "journal.due"

    # خودِ سیستم پلاگین
    PLUGIN_REGISTERED = "plugin.registered"
    PLUGIN_FAILED = "plugin.failed"
    PLUGIN_DISABLED = "plugin.disabled"

    # مراحل pipeline (توسط PipelineRunner منتشر می‌شوند)
    STAGE_START = "stage.start"
    STAGE_DONE = "stage.done"

    ALL = (CYCLE_START, MARKET_COLLECTED, JOURNAL_RESOLVED,
           FUNDAMENTAL_COLLECTED, VETOES_COMPUTED, JUDGE_DONE,
           SIGNAL_CREATED, SIGNAL_SENT, ALERTS_FIRED, REPORT_RENDERED,
           TELEGRAM_SENT, CYCLE_END, NEWS_BREAKING, BRIEFING_DUE,
           JOURNAL_DUE, PLUGIN_REGISTERED, PLUGIN_FAILED, PLUGIN_DISABLED,
           STAGE_START, STAGE_DONE)


class EventBus:
    """pub/sub حداقلی — بدون وابستگی خارجی."""

    def __init__(self) -> None:
        self._subs: Dict[str, List[Callable[[Any], None]]] = {}

    def on(self, event: str, fn: Callable[[Any], None]) -> Callable[[], None]:
        """ثبت listener؛ خروجی = تابع unsubscribe."""
        self._subs.setdefault(event, []).append(fn)

        def off() -> None:
            lst = self._subs.get(event)
            if lst and fn in lst:
                lst.remove(fn)
        return off

    def emit(self, event: str, payload: Any = None) -> List[Tuple[Callable, str]]:
        """اجرای listenerها به ترتیب ثبت.

        خروجی: فهرست (listener, error) برای listenerهایی که خطا دادند —
        خودِ emit هرگز استثنا پرتاب نمی‌کند (ایزولاسیون کامل).
        """
        errors: List[Tuple[Callable, str]] = []
        for fn in list(self._subs.get(event, ())):   # کپی: حین اجرا unsubscribe امن باشد
            try:
                fn(payload)
            except Exception as e:                  # noqa: BLE001 — عمدی: قرنطینه
                errors.append((fn, str(e)))
        return errors

    def listener_count(self, event: str) -> int:
        return len(self._subs.get(event, ()))
