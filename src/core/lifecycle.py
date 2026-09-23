# -*- coding: utf-8 -*-
"""Lifecycle پلاگین‌ها — ماشین حالت + قرنطینهٔ خطا (فاز ۱).

اصل Failure Isolation (که در این پروژه از روز اول قاعده بوده و اینجا
codify می‌شود): خطای یک پلاگین هرگز نباید کل چرخه را بیندازد. پلاگینِ
خطاکرده به وضعیت FAILED می‌رود و «قرنطینه» می‌شود؛ بقیه سالم می‌مانند و
مصرف‌کننده‌ها مقدار unavailable دریافت می‌کنند (امتیاز صادقانهٔ ۰ —
نه دادهٔ جعلی).

گذارهای مجاز:
    REGISTERED → RESOLVED → INITIALIZED → STARTED → STOPPED → DISPOSED
    هر وضعیت (به‌جز DISPOSED) → FAILED   (با ثبت PluginFailure)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timezone


class PluginState(str, Enum):
    REGISTERED = "registered"
    RESOLVED = "resolved"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    DISPOSED = "disposed"
    FAILED = "failed"


# گذارهای مجاز ماشین حالت
_ALLOWED: Dict[PluginState, tuple] = {
    PluginState.REGISTERED: (PluginState.RESOLVED, PluginState.FAILED),
    PluginState.RESOLVED: (PluginState.INITIALIZED, PluginState.FAILED),
    PluginState.INITIALIZED: (PluginState.STARTED, PluginState.STOPPED, PluginState.FAILED),
    PluginState.STARTED: (PluginState.STOPPED, PluginState.FAILED),
    PluginState.STOPPED: (PluginState.STARTED, PluginState.DISPOSED, PluginState.FAILED),
    PluginState.DISPOSED: (),
    PluginState.FAILED: (),          # قرنطینه: بازگشت خودکار ندارد (ریست دستی در فاز ۳)
}


@dataclass
class PluginFailure:
    """رکورد یک خطای قرنطینه‌شده — برای لاگ و رویداد `plugin.failed`."""

    plugin_id: str
    phase: str                       # initialize | start | stop | dispose | run
    error: str
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def fa_message(self) -> str:
        return f"[!] پلاگین «{self.plugin_id}» در {self.phase} خطا داد و غیرفعال شد: {self.error[:120]}"


class InvalidTransitionError(RuntimeError):
    """گذار نامعتبر در ماشین حالت — نشانهٔ باگ داخلی، نه خطای پلاگین."""


def _hook(instance: Any, name: str) -> Optional[Callable]:
    """هوک اختیاری روی نمونهٔ پلاگین — اگر callable بود برگردان."""
    fn = getattr(instance, name, None)
    return fn if callable(fn) else None


class LifecycleManager:
    """گذار وضعیت رکوردهای پلاگین (record = PluginRecord در registry.py).

    این کلاس عمداً registry را import نمی‌کند (duck-typing) تا وابستگی
    حلقوی نشود؛ رکورد باید این فیلدها را داشته باشد:
        manifest, factory, state, instance, error
    """

    def __init__(self, context: Any = None,
                 on_failure: Optional[Callable[[PluginFailure], None]] = None):
        self.context = context        # در فاز ۲: حداقل {"cfg": ...}
        self.on_failure = on_failure  # معمولاً bus.emit("plugin.failed", ...)
        self.failures: List[PluginFailure] = []

    # ── ابزار داخلی ────────────────────────────────────────────
    def _transition(self, record: Any, to: PluginState) -> None:
        if to not in _ALLOWED[record.state]:
            raise InvalidTransitionError(
                f"گذار {record.state.value} → {to.value} برای پلاگین "
                f"«{record.manifest.id}» مجاز نیست")
        record.state = to

    def _quarantine(self, record: Any, phase: str, exc: BaseException) -> PluginFailure:
        f = PluginFailure(plugin_id=record.manifest.id, phase=phase, error=str(exc))
        record.state = PluginState.FAILED
        record.error = f"{phase}: {exc}"
        self.failures.append(f)
        if self.on_failure is not None:
            try:
                self.on_failure(f)
            except Exception:
                pass                  # خودِ گزارشگر خطا هرگز چرخه را نمی‌اندازد
        return f

    # ── گذارها ─────────────────────────────────────────────────
    def initialize(self, record: Any) -> Optional[PluginFailure]:
        """RESOLVED → INITIALIZED: ساخت نمونه با factory + هوک initialize()."""
        try:
            if record.instance is None:
                if record.factory is None:
                    raise ValueError("factory تعریف نشده — پلاگین قابل ساخت نیست")
                record.instance = (record.factory(self.context)
                                   if self.context is not None
                                   else record.factory())
            hook = _hook(record.instance, "initialize")
            if hook is not None:
                hook()
            self._transition(record, PluginState.INITIALIZED)
            return None
        except InvalidTransitionError:
            raise                     # باگ داخلی چارچوب — پرسروصدا، نه قرنطینه
        except Exception as e:        # خطای پلاگین — قرنطینه، استثنا بیرون نمی‌رود
            return self._quarantine(record, "initialize", e)

    def start(self, record: Any) -> Optional[PluginFailure]:
        """INITIALIZED → STARTED (هوک start() اختیاری)."""
        try:
            hook = _hook(record.instance, "start")
            if hook is not None:
                hook()
            self._transition(record, PluginState.STARTED)
            return None
        except InvalidTransitionError:
            raise
        except Exception as e:
            return self._quarantine(record, "start", e)

    def stop(self, record: Any) -> Optional[PluginFailure]:
        """STARTED → STOPPED (هوک stop() اختیاری؛ مثل disconnect امروز)."""
        try:
            hook = _hook(record.instance, "stop")
            if hook is not None:
                hook()
            self._transition(record, PluginState.STOPPED)
            return None
        except InvalidTransitionError:
            raise
        except Exception as e:
            return self._quarantine(record, "stop", e)

    def dispose(self, record: Any) -> Optional[PluginFailure]:
        """STOPPED → DISPOSED (هوک dispose() اختیاری؛ نمونه دور انداخته می‌شود)."""
        try:
            hook = _hook(record.instance, "dispose")
            if hook is not None:
                hook()
            self._transition(record, PluginState.DISPOSED)
            record.instance = None
            return None
        except InvalidTransitionError:
            raise
        except Exception as e:
            return self._quarantine(record, "dispose", e)

    # ── دسته‌جمعی (به ترتیب resolve‌شده) ───────────────────────
    def initialize_all(self, records: List[Any], start: bool = False) -> List[PluginFailure]:
        """همهٔ رکوردهای RESOLVED را (به ترتیب ورودی) initialize می‌کند.

        پلاگین FAILED از زنجیره حذف نمی‌شود تا بقیه بخورند زمین — هر رکورد
        مستقل است؛ فقط آنکه خطا داده قرنطینه می‌شود.
        """
        for r in records:
            if r.state is PluginState.RESOLVED:
                self.initialize(r)
        if start:
            for r in records:
                if r.state is PluginState.INITIALIZED:
                    self.start(r)
        return list(self.failures)
