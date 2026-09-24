# -*- coding: utf-8 -*-
"""پلاگین اعلان — تلگرام (فاز ۲، فقط دسکتاپ).

بدنهٔ واقعی ارسال (خواندن bot_token/chat_id، لاگ‌های فارسی، مقدار بازگشتی)
در فاز ۳ بایت‌به‌بایت از `src/engine.py::_send_telegram` به اینجا منتقل شد؛
engine حالا فقط wrapper نازکی برای سازگاری امضای تاریخی دارد. میخ‌های
رفتاری: tests/test_engine_switch.py (سه مسیر ارسال).

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
        """بدنهٔ _send_telegram سابق — فاز ۳ بایت‌به‌بایت به اینجا منتقل شد.

        پیام‌های لاگ و مقدارهای بازگشتی با میخ‌های tests/test_engine_switch.py
        پین شده‌اند. guard «تنظیم نشده» عمداً همین‌جاست (نه bind شدن به
        telegram.send_reports در مانیفست) تا نبودِ پلاگین هرگز این مسیرِ
        graceful را از engine نگیرد.
        """
        log = on_log or _noop_log
        tg = cfg.get("telegram") or {}
        token = str(tg.get("bot_token") or "").strip()
        chat_id = str(tg.get("chat_id") or "").strip()
        if not (tg.get("send_reports", True) and token and chat_id):
            log(f"[i] تلگرام تنظیم نشده — {label} فقط در پنل/کنسول نمایش داده می‌شود")
            return False, "تنظیم نشده"
        log(f"📱 ارسال {label} به تلگرام...")
        from ..notify import telegram            # import تنبل (بدون چرخه، سبک)
        ok, msg = telegram.send_message(token, chat_id, text)
        log(("✅ " if ok else "❌ ") + f"تلگرام: {msg}")
        return ok, msg


def plugins() -> List[Tuple[PluginManifest, Any]]:
    return [
        (PluginManifest(
            id="notify-telegram", version="1.0.0",
            provides=["odin.notify@1"],
            # فاز ۷ — بازبینی انجام شد: bind به telegram.send_reports امن است،
            # چون wrapper تاریخیِ engine از فاز ۳ برای notifier=None شاخهٔ
            # graceful دارد با *همان* پیام و مقدار بازگشتیِ مسیر «تنظیم
            # نشده» («[i] تلگرام تنظیم نشده — …» / (False, "تنظیم نشده")) —
            # پس نبودِ پلاگین هرگز این مسیر را از engine نمی‌گیرد (وعدهٔ
            # کامنت فاز ۳). guard داخل بدنهٔ send هم باقی است (token/chat_id
            # خالی با send_reports=true → همان خروجی).
            config={"section": "telegram", "enabled_key": "send_reports",
                    "default": True},
            platforms=["desktop"],
            stage="dispatch_signals", priority=10, optional=True),
         lambda _ctx: TelegramNotifier()),
    ]
