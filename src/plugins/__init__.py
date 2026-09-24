# -*- coding: utf-8 -*-
"""پلاگین‌های داخلی (built-in) ODIN — نقطهٔ ورود واحد `build_default_registry` (فاز ۲).

این پکیج **هیچ منطقی ندارد** — فقط adapterهای نازک (delegation خالص) دور
ماژول‌های موجود را با مانیفست‌های اعلانی در registry ثبت می‌کند. منطق واقعی
در همان جای قبلی است (src/data، src/analysis، src/judge، ...) و در فاز ۲
هیچ مصرف‌کننده‌ای (engine/panel/main) از اینجا استفاده نمی‌کند.

ورودی فاز ۳: engine به‌جای import مستقیم فیچرها، از
`build_default_registry(cfg)` و `registry.get(contract)` مصرف می‌کند.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.config_bridge import apply_config_state
from ..core.pipeline import STAGES
from ..core.registry import PluginRegistry
from ..core.resolver import resolve
from . import (alerts, analysis, data, fundamental, judge, journal, notify,  # noqa: F401
               report, strategies)

# ترتیب ثبت = ترتیب اعلامی زیر (قطعی؛ tie-break در resolver هم order است)
_MODULES = (data, analysis, fundamental, judge, strategies, journal, notify,
            alerts, report)


def build_default_registry(cfg: Optional[dict] = None,
                           platform: str = "desktop") -> Tuple[PluginRegistry, Dict[str, Any]]:
    """رجیستری کاملِ پلاگین‌های داخلی را می‌سازد.

    Args:
        cfg:      پیکربندی بارگذاری‌شده (مثل خروجی load_config). None → load_config()
        platform: "desktop" | "android" — فقط پلاگین‌های همان پلتفرم ثبت می‌شوند

    Returns:
        (registry, info) که info:
            cfg      — همان پیکربندی (برای factoryها در context)
            platform — پلتفرم ثبت‌شده
            context  — context مشترک factoryها: {"cfg": ..., "platform": ...}
            order    — ترتیب resolve‌شدهٔ idها (توپولوژیک + priority)
            log      — خطوط لاگ فارسی (ثبت/غیرفعال‌سازی) برای تشخیص
            disabled — [{id, reason}] پلاگین‌هایی که resolver به‌دلیل
                       وابستگی مفقود غیرفعال کرد
    """
    if cfg is None:
        from ..config import load_config
        cfg = load_config()

    reg = PluginRegistry(known_stages=STAGES)
    log: List[str] = []

    for mod in _MODULES:
        for manifest, factory in mod.plugins():
            if platform not in manifest.platforms:
                continue
            rec = reg.register(manifest, factory)
            log.append(f"[plugin] «{rec.id}» ثبت شد — فراهم‌کنندهٔ "
                       f"{', '.join(manifest.provides)} (مرحله: {manifest.stage})")

    # فعال/غیرفعال طبق *همان کلیدهای موجود* config (بدون کلید جدید)
    enabled = apply_config_state(reg, cfg)
    for pid, on in enabled.items():
        if not on:
            log.append(f"[plugin] «{pid}» طبق تنظیمات غیرفعال است")

    # ترتیب‌دهی توپولوژیک + آبشارِ وابستگی مفقود (بدون کرش)
    order = resolve(reg.all())
    disabled = [{"id": r.id, "reason": r.disabled_reason}
                for r in reg.all() if r.disabled_reason]
    for d in disabled:
        log.append(f"[plugin] «{d['id']}» توسط resolver غیرفعال شد — {d['reason']}")

    info = {"cfg": cfg, "platform": platform,
            # registry در context (فاز ۴): judge-core قواعد وتو/شاهد/ریسک را
            # از همان registry‌ای می‌خواند که خودش در آن ثبت شده — کلید
            # افزودنی است و بقیهٔ factoryها (که ctx را نادیده می‌گیرند) بی‌اثر.
            "context": {"cfg": cfg, "platform": platform, "registry": reg},
            "order": [r.id for r in order],
            "log": log, "disabled": disabled}
    return reg, info


__all__ = ["build_default_registry"]
