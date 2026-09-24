# -*- coding: utf-8 -*-
"""پل پیکربندی — مانیفست پلاگین ↔ کلیدهای *موجود* config (فاز ۱).

اصل حفظ رفتار (مهم‌ترین قاعدهٔ این مهاجرت):
  • مانیفست هر پلاگین به همان کلیدی اشاره می‌کند که امروز هم وجود دارد
    (news.enabled، judge.enabled، fundamental.enabled و ...). هیچ کلید
    جدیدی به config.yaml / O.CONFIG اضافه نمی‌شود.
  • بخش اختیاری `plugins:` در config فقط «override» است و پیش‌فرضِ خالی
    دارد؛ یعنی وقتی کاربر چیزی ننوشته، رفتار دقیقاً امروز است.
    (کلیدهای این بخش در فاز ۷ در config.yaml/config.js مستندِ کاربری شدند.)

ترتیب اولویت (بالا = برنده):
  ۱) cfg["plugins"][plugin_id]["enabled"]     (override صریح کاربر)
  ۲) cfg[section][enabled_key]                (کلید فیچری موجود — مثل امروز)
  ۳) manifest.config["default"]               (پیش‌فرض مانیفست)
  ۴) True                                     (اگر مانیفست config نداشت)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .manifest import PluginManifest


def _resolve_enabled_key(section: Any, key: str) -> tuple:
    """مقدارِ کلید (مسطح یا dot-path) درون بخش — (مقدار، پیدا شد).

    فاز ۷: `enabled_key` می‌تواند مسیر نقطه‌ای باشد (مثل "veto.weekend"
    در بخش judge) تا کلیدهای تودرتوی *موجود* هم زیر مانیفست بیایند —
    بدون هیچ کلید جدیدی. مسیر مفقود → (None, False) → پیش‌فرض مانیفست.
    """
    cur = section
    for part in str(key).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None, False
        cur = cur[part]
    return cur, True


def plugin_enabled(cfg: Dict[str, Any], manifest: PluginManifest) -> bool:
    """آیا این پلاگین طبق config فعال است؟ (تصمیم خالص — بدون side-effect)"""
    cfg = cfg or {}

    # ۱) override صریح در بخش plugins
    over = ((cfg.get("plugins") or {}).get(manifest.id) or {})
    if isinstance(over, dict) and "enabled" in over:
        return bool(over["enabled"])

    # ۲) کلید فیچری موجود (مسطح یا dot-path — فاز ۷)
    c = manifest.config
    if isinstance(c, dict) and c.get("section"):
        section = cfg.get(c["section"])
        if isinstance(section, dict):
            val, found = _resolve_enabled_key(section, c.get("enabled_key", "enabled"))
            if found:
                return bool(val)
        # ۳) پیش‌فرض مانیفست
        return bool(c.get("default", True))

    # ۴) بدون اتصال config → فعال
    return True


def plugin_config(cfg: Dict[str, Any], manifest: PluginManifest) -> dict:
    """بخش config این پلاگین (dict) — همان چیزی که توابع فعلی می‌گیرند.

    overrideهای `plugins[id].config` عمیق روی بخش ادغام می‌شوند (فاز ۷ مستند شد؛
    هنوز مصرف‌کننده‌ای ندارد) — امروز خروجی == cfg[section] است.
    """
    cfg = cfg or {}
    c = manifest.config or {}
    section = cfg.get(c.get("section", ""), None) if c.get("section") else None
    base = dict(section) if isinstance(section, dict) else {}
    over = ((cfg.get("plugins") or {}).get(manifest.id) or {}).get("config") or {}
    if isinstance(over, dict):
        base = _deep_merge(base, over)
    return base


def _deep_merge(base: dict, over: dict) -> dict:
    """ادغام عمیق — همان معنای _deep_merge در src/config.py (کپی عمدی:
    هسته نباید از ماژول‌های فیچر/دسکتاپ import کند)."""
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def apply_config_state(registry: Any, cfg: Dict[str, Any]) -> Dict[str, bool]:
    """وضعیت enabled همهٔ پلاگین‌های ثبت‌شده را از config به‌روز می‌کند.

    خروجی: {plugin_id: enabled} — برای لاگ تشخیصی. خودِ registry.disable/
    enable صدا زده می‌شود تا `active` و status() صادق بمانند.
    """
    out: Dict[str, bool] = {}
    for rec in registry.all():
        on = plugin_enabled(cfg, rec.manifest)
        (registry.enable if on else registry.disable)(rec.id)
        out[rec.id] = on
    return out
