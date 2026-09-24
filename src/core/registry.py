# -*- coding: utf-8 -*-
"""رجیستری پلاگین‌ها — ثبت، جست‌وجو با قرارداد، enable/disable (فاز ۱).

نکتهٔ طراحی: چند پلاگین می‌توانند یک قرارداد را فراهم کنند (مثل
data-yahoo و data-twelvedata و data-auto برای odin.data.market@1) — این
مشروع است چون انتخاب بینشان «config-driven» است (کلید data_source)، نه
تصادفی. `get()` اولویت‌دار (priority، سپس ترتیب ثبت) و `providers()` همه را
به ترتیب قطعی برمی‌گرداند؛ انتخاب نهایی در فاز ۳ با predicate انجام می‌شود.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .lifecycle import PluginState
from .manifest import PluginManifest


class DuplicatePluginError(ValueError):
    """ثبت دو پلاگین با یک id — پرسروصدا (بی‌صدا اولین را نگه نمی‌داریم)."""


@dataclass
class PluginRecord:
    """رکورد ثبت‌شدهٔ یک پلاگین در رجیستری."""

    manifest: PluginManifest
    factory: Optional[Callable[..., Any]] = None
    enabled: bool = True                    # کلید فعال/غیرفعال (config bridge)
    state: PluginState = PluginState.REGISTERED
    instance: Any = None                    # پس از initialize
    error: str = ""                         # آخرین خطای قرنطینه‌شده
    order: int = 0                          # ترتیب ثبت — tie-breaker قطعی
    disabled_reason: str = ""               # چرا resolver غیرفعالش کرده (فارسی)

    @property
    def id(self) -> str:
        return self.manifest.id

    @property
    def active(self) -> bool:
        """فعال = enabled (توسط config/کاربر) و disable نشده (توسط resolver) و خراب نیست."""
        return (self.enabled and not self.disabled_reason
                and self.state is not PluginState.FAILED)

    def status_dict(self) -> dict:
        return {"id": self.id, "version": self.manifest.version,
                "provides": list(self.manifest.provides),
                "enabled": self.enabled, "state": self.state.value,
                "disabled_reason": self.disabled_reason, "error": self.error}


class PluginRegistry:
    """رجیستری مرکزی — کوچک، قطعی، بدون side-effect پنهان."""

    def __init__(self, known_stages: Optional[tuple] = None):
        self._records: Dict[str, PluginRecord] = {}
        self._order = 0
        self.known_stages = known_stages    # اگر داده شود، validate مرحله را هم می‌سنجد

    # ── ثبت ────────────────────────────────────────────────────
    def register(self, manifest: PluginManifest,
                 factory: Optional[Callable[..., Any]] = None) -> PluginRecord:
        manifest.validate(known_stages=self.known_stages)
        if manifest.id in self._records:
            raise DuplicatePluginError(
                f"پلاگین «{manifest.id}» قبلاً ثبت شده است — id باید یکتا باشد")
        rec = PluginRecord(manifest=manifest, factory=factory or manifest.factory,
                           order=self._order)
        self._order += 1
        self._records[manifest.id] = rec
        return rec

    # ── جست‌وجو ────────────────────────────────────────────────
    def by_id(self, plugin_id: str) -> Optional[PluginRecord]:
        return self._records.get(plugin_id)

    def providers(self, contract_id: str, only_active: bool = True) -> List[PluginRecord]:
        """همهٔ فراهم‌کنندگان یک قرارداد، به ترتیب قطعی (priority، سپس ثبت)."""
        out = [r for r in self._records.values()
               if contract_id in r.manifest.provides
               and (r.active or not only_active)]
        return sorted(out, key=lambda r: (r.manifest.priority, r.order))

    def get(self, contract_id: str) -> Optional[PluginRecord]:
        """یک فراهم‌کننده (بالاترین اولویت) یا None — هیچ‌وقت استثنا نه."""
        ps = self.providers(contract_id)
        return ps[0] if ps else None

    def by_stage(self, stage: str, only_active: bool = True) -> List[PluginRecord]:
        """پلاگین‌های یک مرحلهٔ pipeline به ترتیب (priority، سپس ثبت)."""
        out = [r for r in self._records.values()
               if r.manifest.stage == stage
               and (r.active or not only_active)]
        return sorted(out, key=lambda r: (r.manifest.priority, r.order))

    def all(self, only_active: bool = False) -> List[PluginRecord]:
        out = list(self._records.values())
        if only_active:
            out = [r for r in out if r.active]
        return sorted(out, key=lambda r: r.order)

    # ── enable / disable (سطح کاربر/تنظیمات) ────────────────────
    def enable(self, plugin_id: str) -> bool:
        rec = self._records.get(plugin_id)
        if rec is None:
            return False
        rec.enabled = True
        return True

    def disable(self, plugin_id: str) -> bool:
        rec = self._records.get(plugin_id)
        if rec is None:
            return False
        rec.enabled = False
        return True

    def status(self) -> List[dict]:
        """خلاصهٔ وضعیت همهٔ پلاگین‌ها — برای لاگ/تشخیص.

        (نمایش در UI: به بعد از مهاجرت موکول شد — تصمیم فاز ۷ با تأیید مالک؛
        API آماده است و smoke_plugins/test_plugins مصرفش را پین کرده‌اند.)
        """
        return [r.status_dict() for r in self.all()]
