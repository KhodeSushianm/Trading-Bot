# -*- coding: utf-8 -*-
"""مانیفست پلاگین — شناسنامهٔ اعلانی هر پلاگین (فاز ۱).

مانیفست «داده» است، نه کد: اینکه پلاگین چیست، چه قراردادی فراهم می‌کند،
به چه چیزی وابسته است، از کدام بخش config فعال/غیرفعال می‌شود، در کدام
مرحلهٔ pipeline و با چه اولویتی می‌دود. همان ساختار در JS (فاز ۵) با
object ساده بازتولید می‌شود تا دو زبان یک معنا داشته باشند.

قاعدهٔ طلایی حفظ رفتار: `config` مانیفست به کلیدهای *موجود* config.yaml
(و O.CONFIG اندروید) اشاره می‌کند — هیچ کلید جدیدی در فازهای ۱–۶ اضافه
نمی‌شود، پس «فعال/غیرفعال» دقیقاً همان معنای امروز را دارد.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .contracts import is_valid_contract_id, is_wellformed_contract_id

PLUGIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
VALID_PLATFORMS = ("desktop", "android")


class InvalidManifestError(ValueError):
    """مانیفست نامعتبر — پرسروصدا و با پیام فارسی (فلسفهٔ پروژه: بی‌صدا نه)."""


@dataclass
class PluginManifest:
    """شناسنامهٔ پلاگین.

    Fields:
        id:        شناسهٔ یکتا (kebab-case) — مثل "fundamental-calendar"
        version:   semver سادهٔ خود پلاگین — مثل "1.0.0"
        provides:  قراردادهایی که فراهم می‌کند — ["odin.fundamental.calendar@1"]
        requires:  وابستگی‌های «سخت» — اگر فراهم‌کننده‌اش فعال نباشد، این
                   پلاگین هم غیرفعال می‌شود (با لاگ فارسی، بدون کرش).
                   وابستگی نرم (مثل judge که cal_snap=None را تحمل می‌کند)
                   عمداً در requires نمی‌آید — همان رفتار امروز.
        config:    اتصال به کلید فعال‌بودنِ *موجود*:
                   {"section": "fundamental", "enabled_key": "enabled",
                    "default": True}
        platforms: ["desktop", "android"] — کجا ثبت می‌شود
        stage:     نام مرحلهٔ pipeline (فهرست معتبر در pipeline.STAGES)
        priority:  ترتیب درون مرحله (عدد کوچک‌تر = زودتر؛ tie-break = ترتیب ثبت)
        optional:  اگر True، نبودِ این پلاگین برای مصرف‌کننده‌ها «unavailable»
                   است نه کرش — که مطابق قاعدهٔ صداقت پروژه است.
        factory:   callable(context) → نمونهٔ پلاگین. context در فاز ۲ تعریف
                   نهایی می‌شود (حداقل: cfg). None فقط در تست‌های اسکلت مجاز است.
    """

    id: str
    version: str
    provides: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    config: Optional[Dict[str, Any]] = None
    platforms: List[str] = field(default_factory=lambda: list(VALID_PLATFORMS))
    stage: str = ""
    priority: int = 100
    optional: bool = True
    factory: Optional[Callable[..., Any]] = None

    def validate(self, known_stages: Optional[tuple] = None) -> "PluginManifest":
        """اعتبارسنجی کامل؛ در صورت مشکل InvalidManifestError با پیام فارسی."""
        if not self.id or not PLUGIN_ID_RE.match(self.id):
            raise InvalidManifestError(
                f"شناسهٔ پلاگین نامعتبر: {self.id!r} — باید kebab-case باشد "
                f"(حروف کوچک/عدد/خط-تیره/نقطه/زیرخط، بدون حرف اضافه در ابتدا)")
        if not VERSION_RE.match(self.version or ""):
            raise InvalidManifestError(
                f"نسخهٔ پلاگین «{self.id}» باید semver ساده باشد (مثل 1.0.0)، "
                f"نه {self.version!r}")
        if not self.provides:
            raise InvalidManifestError(
                f"پلاگین «{self.id}» هیچ قراردادی فراهم نمی‌کند — provides خالی است")
        for cid in self.provides:
            if not is_wellformed_contract_id(cid):
                raise InvalidManifestError(
                    f"شناسهٔ قرارداد نامعتبر در provides پلاگین «{self.id}»: {cid!r} "
                    f"— شکل معتبر: name.domain@1")
            if not is_valid_contract_id(cid):
                raise InvalidManifestError(
                    f"قرارداد ناشناخته «{cid}» در پلاگین «{self.id}» — هسته فقط "
                    f"قراردادهای ثبت‌شده در core.contracts.CONTRACTS را می‌شناسد "
                    f"(قرارداد جدید = تصمیم معماری، نه افزودهٔ سرخود)")
        for cid in self.requires:
            if not is_wellformed_contract_id(cid):
                raise InvalidManifestError(
                    f"شناسهٔ قرارداد نامعتبر در requires پلاگین «{self.id}»: {cid!r}")
            if not is_valid_contract_id(cid):
                raise InvalidManifestError(
                    f"قرارداد ناشناخته «{cid}» در requires پلاگین «{self.id}»")
        if self.provides and self.requires:
            overlap = set(self.provides) & set(self.requires)
            if overlap:
                raise InvalidManifestError(
                    f"پلاگین «{self.id}» نمی‌تواند به قرارداد خودش وابسته باشد: "
                    f"{sorted(overlap)}")
        if self.config is not None:
            if not isinstance(self.config, dict):
                raise InvalidManifestError(
                    f"config پلاگین «{self.id}» باید dict باشد")
            for key in ("section", "enabled_key"):
                if key not in self.config:
                    raise InvalidManifestError(
                        f"config پلاگین «{self.id}» کلید «{key}» ندارد")
            if not isinstance(self.config.get("default", True), bool):
                raise InvalidManifestError(
                    f"config.default پلاگین «{self.id}» باید bool باشد")
        for p in self.platforms:
            if p not in VALID_PLATFORMS:
                raise InvalidManifestError(
                    f"پلتفرم نامعتبر «{p}» در پلاگین «{self.id}» "
                    f"(مجاز: {' | '.join(VALID_PLATFORMS)})")
        if not self.platforms:
            raise InvalidManifestError(f"platforms پلاگین «{self.id}» خالی است")
        if not self.stage:
            raise InvalidManifestError(f"stage پلاگین «{self.id}» خالی است")
        if known_stages is not None and self.stage not in known_stages:
            raise InvalidManifestError(
                f"مرحلهٔ ناشناخته «{self.stage}» برای پلاگین «{self.id}» — "
                f"مراحل معتبر: {', '.join(known_stages)}")
        if not isinstance(self.priority, int):
            raise InvalidManifestError(
                f"priority پلاگین «{self.id}» باید int باشد، نه {type(self.priority).__name__}")
        return self
