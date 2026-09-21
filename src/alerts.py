#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""هشدارهای قیمت (v0.19.0) — همزاد دقیقِ js/alerts.js اندروید.

سطح قیمتیِ کاربر در هر چرخهٔ تحلیل (run_cycle) در برابر قیمت آخرِ
نمادها بررسی می‌شود؛ فعال‌شدن → اعلان در پنل + tray + تلگرام (اگر وصل باشد).

رکورد: {id, symbol, dir, price, pip, sticky, created_at, last_fired}
  id = symbol|dir|price (یکتا)
  sticky=False → با اولین فعال‌شدن حذف می‌شود (اعلان دوبله نمی‌رود)
  sticky=True  → می‌ماند؛ کول‌داون ۶۰ دقیقه‌ای
ذخیره‌سازی: alerts.json در پوشهٔ دادهٔ اپ (app_paths.data_dir).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src import app_paths

MAX_ALERTS = 20
STICKY_COOLDOWN_SEC = 60 * 60


def _file() -> Path:
    d = app_paths.data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "alerts.json"


def load_alerts() -> list:
    try:
        f = _file()
        if not f.exists():
            return []
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(rows: list) -> None:
    try:
        _file().write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def alert_id(symbol: str, direction: str, price: float) -> str:
    return f"{symbol}|{direction}|{price}"


def add_alert(symbol: str, direction: str, price: float,
              sticky: bool = False, pip: float = 0.0001) -> tuple[bool, str]:
    """→ (موفقیت, پیام/دلیل)."""
    try:
        price = float(price)
    except (TypeError, ValueError):
        return False, "invalid"
    if not symbol or price <= 0:
        return False, "invalid"
    direction = "below" if direction == "below" else "above"
    rows = load_alerts()
    aid = alert_id(symbol, direction, price)
    if any(r.get("id") == aid for r in rows):
        return False, "duplicate"
    if len(rows) >= MAX_ALERTS:
        return False, "max"
    rows.insert(0, {
        "id": aid, "symbol": symbol, "dir": direction, "price": price,
        "pip": pip if pip and pip > 0 else 0.0001,
        "sticky": bool(sticky),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_fired": None,
    })
    _save(rows)
    return True, "ok"


def remove_alert(aid: str) -> None:
    rows = [r for r in load_alerts() if r.get("id") != aid]
    _save(rows)


def _get(a, key, default=None):
    """analyses ممکن است dataclass یا dict باشد — دسترسی یکسان."""
    if isinstance(a, dict):
        return a.get(key, default)
    return getattr(a, key, default)


def check_alerts(analyses, now: datetime | None = None) -> list:
    """بررسی عبور قیمت. → فهرست رکوردهای فعال‌شده (همان dict ذخیره‌شده)."""
    rows = load_alerts()
    if not rows or not analyses:
        return []
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    by_sym = {}
    for a in analyses:
        by_sym[_get(a, "symbol")] = a
    fired, keep, dirty = [], [], False
    for r in rows:
        an = by_sym.get(r.get("symbol"))
        price = _get(an, "price") if an is not None else None
        if price is None or not isinstance(price, (int, float)):
            keep.append(r)
            continue
        hit = price >= r["price"] if r.get("dir") == "above" else price <= r["price"]
        if not hit:
            keep.append(r)
            continue
        if r.get("sticky"):
            lf = r.get("last_fired")
            elapsed = None
            if lf:
                try:
                    last = datetime.fromisoformat(lf)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    elapsed = (now - last).total_seconds()
                except Exception:
                    elapsed = None
            if elapsed is None or elapsed >= STICKY_COOLDOWN_SEC:
                r["last_fired"] = now.isoformat()
                r["_price"] = float(price)
                fired.append(dict(r))
                keep.append(r)
                dirty = True
            else:
                keep.append(r)
        else:
            r["_price"] = float(price)
            fired.append(dict(r))
            dirty = True     # یک‌بارمصرف → حذف (در keep نمی‌آید)
    if dirty or len(keep) != len(rows):
        _save(keep)
    return fired
