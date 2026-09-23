# -*- coding: utf-8 -*-
"""پلاگین‌های فاندامنتال — تقویم اقتصادی و اخبار (فاز ۲).

قاعدهٔ adapter: فقط delegation با همان defaults توابع موجود؛ منطق در
src/fundamental/* دست‌نخورده است (هر دو تابع «هرگز استثنا پرتاب نمی‌کنند»
و snapshot با ok=False برمی‌گردانند — همان حلقهٔ صداقت).
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional, Tuple

from ..core.manifest import PluginManifest


class CalendarPlugin:
    def fetch_calendar(self, cfg: Optional[dict] = None,
                       on_log: Optional[Callable[[str], None]] = None,
                       use_cache: bool = True, timeout: int = 15) -> Any:
        from ..fundamental.calendar import fetch_calendar
        return fetch_calendar(cfg, on_log=on_log, use_cache=use_cache, timeout=timeout)

    def upcoming_events(self, snap: Any, now: Optional[Any] = None,
                        hours: float = 72.0,
                        impacts: Tuple[str, ...] = ("HIGH", "MEDIUM"),
                        countries: Optional[Iterable[str]] = None,
                        limit: Optional[int] = None) -> List[Any]:
        from ..fundamental.calendar import upcoming_events
        return upcoming_events(snap, now=now, hours=hours, impacts=impacts,
                               countries=countries, limit=limit)

    def veto_for_symbol(self, snap: Any, base: str, quote: str,
                        now: Any, minutes: float = 30.0) -> List[Any]:
        from ..fundamental.calendar import veto_for_symbol
        return veto_for_symbol(snap, base, quote, now, minutes=minutes)


class NewsPlugin:
    def fetch_news(self, cfg: Optional[dict] = None,
                   on_log: Optional[Callable[[str], None]] = None,
                   max_age_hours: Optional[float] = None) -> Any:
        from ..fundamental.news import fetch_news
        return fetch_news(cfg, on_log=on_log, max_age_hours=max_age_hours)


def plugins() -> List[Tuple[PluginManifest, Any]]:
    return [
        (PluginManifest(
            id="fundamental-calendar", version="1.0.0",
            provides=["odin.fundamental.calendar@1"],
            config={"section": "fundamental", "enabled_key": "enabled", "default": True},
            platforms=["desktop", "android"],
            stage="collect_fundamental", priority=10, optional=True),
         lambda _ctx: CalendarPlugin()),
        (PluginManifest(
            id="fundamental-news", version="1.0.0",
            provides=["odin.fundamental.news@1"],
            config={"section": "news", "enabled_key": "enabled", "default": True},
            platforms=["desktop", "android"],
            stage="collect_fundamental", priority=20, optional=True),
         lambda _ctx: NewsPlugin()),
    ]
