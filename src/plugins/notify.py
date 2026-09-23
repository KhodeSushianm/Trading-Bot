# -*- coding: utf-8 -*-
"""پلاگین اعلان — تلگرام (فاز ۲، فقط دسکتاپ).

⚠️ delegation موقت: بدنهٔ واقعی ارسال (خواندن bot_token/chat_id از
config.local، تکه‌کردن پیام، log) امروز در `src/engine.py::_send_telegram`
است. برای اینکه منطق **تکثیر نشود** (قاعدهٔ ممنوعهٔ مهاجرت)، این adapter
فعلاً به همان تابع delegate می‌کند. در فاز ۳ جهت وارونه می‌شود: بدنه به
اینجا منتقل و engine مصرف‌کنندهٔ registry می‌شود — با تست طلاییِ قبل/بعد.

اندروید تلگرام ندارد (اعلان‌ها محلی‌اند) → platforms: ["desktop"].
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple

from ..core.manifest import PluginManifest


def _noop_log(_m: str) -> None:
    pass


class TelegramNotifier:
    def send(self, cfg: dict, text: str,
             on_log: Optional[Callable[[str], None]] = None,
             label: str = "گزارش") -> tuple:
        from ..engine import _send_telegram      # موقت تا فاز ۳ (import محلی: بدون چرخه)
        return _send_telegram(cfg, text, on_log or _noop_log, label=label)


def plugins() -> List[Tuple[PluginManifest, Any]]:
    return [
        (PluginManifest(
            id="notify-telegram", version="1.0.0",
            provides=["odin.notify@1"],
            config={"section": "telegram", "enabled_key": "send_reports", "default": True},
            platforms=["desktop"],
            stage="dispatch_signals", priority=10, optional=True),
         lambda _ctx: TelegramNotifier()),
    ]
