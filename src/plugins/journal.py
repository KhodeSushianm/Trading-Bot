# -*- coding: utf-8 -*-
"""پلاگین ژورنال — facade سه جزء موجود store/tracker/stats (فاز ۲).

قاعدهٔ adapter: فقط delegation؛ منطق در src/journal/* دست‌نخورده است.
«حلقهٔ صداقت» (ثبت هر سیگنال و پیگیری نتیجه) دقیقاً با همان معنای امروز
کار می‌کند — ژورنال هیچ‌وقت پاک/بازنویسی نمی‌شود (event-source append-only).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from ..core.manifest import PluginManifest


class JournalPlugin:
    def open(self, path: Optional[Any] = None) -> Any:
        from ..journal.store import Journal
        return Journal(path)

    def resolve_open_signals(self, journal: Any, datasets: Dict[str, Any],
                             now: Optional[Any] = None,
                             cfg: Optional[dict] = None,
                             on_log: Optional[Callable[[str], None]] = None) -> List[Any]:
        from ..journal.tracker import resolve_open_signals
        return resolve_open_signals(journal, datasets, now=now, cfg=cfg, on_log=on_log)

    def compute_stats(self, entries: List[Any], now: Any) -> Any:
        from ..journal.stats import compute_stats
        return compute_stats(entries, now)


def plugins() -> List[Tuple[PluginManifest, Any]]:
    return [
        (PluginManifest(
            id="journal", version="1.0.0",
            provides=["odin.journal@1"],
            # تصمیم نهایی فاز ۷ — config=None می‌ماند (bind نمی‌شود):
            # ۱) ضداسپم (should_send_signal) و ثبت سیگنال حتی با
            #    journal.enabled=false هم باید کار کنند — وگرنه خاموش‌کردن
            #    ژورنال باعث ارسالِ سیگنالِ تکراری می‌شود (رفتار امروز).
            # ۲) resolve_open_signals خودش guard داخلی دارد (enabled=false →
            #    []) — پس «خاموش» صادقانه کار می‌کند بدون غیبتِ پلاگین.
            # یکپارچگیِ enable/disable اینجا یعنی: کلید فیچری + guardهای
            # موجود (engine/بدنه) — نه bind مانیفست. (فقط override صریحِ
            # plugins.journal.enabled=false می‌تواند پلاگین را غایب کند که
            # مصرف‌کننده‌ها در فاز ۷ None-safe شده‌اند.)
            config=None,
            platforms=["desktop", "android"],
            stage="journal_pre", priority=10, optional=True),
         lambda _ctx: JournalPlugin()),
    ]
