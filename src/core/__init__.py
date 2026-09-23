# -*- coding: utf-8 -*-
"""هستهٔ معماری پلاگین ODIN — فاز ۱ (اسکلت، بدون اتصال به engine).

صادرات عمومی (نام‌های کوتاه و پایدار برای فازهای ۲+):

    from src.core import (PluginManifest, PluginRegistry, PluginRecord,
                          resolve, LifecycleManager, PluginState, PluginFailure,
                          EventBus, Events, PipelineRunner, StageResult,
                          STAGES, CONTRACTS, plugin_enabled, plugin_config)

⚠️ در فاز ۱ فقط tests/test_core.py این پکیج را مصرف می‌کند.
   سند طراحی کامل: docs/plugin-architecture-fa.md
"""
from __future__ import annotations

CORE_VERSION = "0.1.0"      # نسخهٔ خودِ هسته ( مستقل از APP_VERSION اپ )

from .bus import EventBus, Events                              # noqa: E402
from .config_bridge import (apply_config_state, plugin_config, # noqa: E402
                            plugin_enabled)
from .contracts import (CONTRACTS, CONTRACT_ID_RE,             # noqa: E402
                        is_valid_contract_id,
                        is_wellformed_contract_id)
from .lifecycle import (InvalidTransitionError, LifecycleManager,  # noqa: E402
                        PluginFailure, PluginState)
from .manifest import InvalidManifestError, PluginManifest     # noqa: E402
from .pipeline import (SCHEDULER_STAGES, STAGES,               # noqa: E402
                       PipelineResult, PipelineRunner, StageResult)
from .registry import DuplicatePluginError, PluginRecord, PluginRegistry  # noqa: E402
from .resolver import CircularDependencyError, resolve         # noqa: E402

__all__ = [
    "CORE_VERSION",
    "EventBus", "Events",
    "apply_config_state", "plugin_config", "plugin_enabled",
    "CONTRACTS", "CONTRACT_ID_RE", "is_valid_contract_id", "is_wellformed_contract_id",
    "InvalidTransitionError", "LifecycleManager", "PluginFailure", "PluginState",
    "InvalidManifestError", "PluginManifest",
    "SCHEDULER_STAGES", "STAGES", "PipelineResult", "PipelineRunner", "StageResult",
    "DuplicatePluginError", "PluginRecord", "PluginRegistry",
    "CircularDependencyError", "resolve",
]
