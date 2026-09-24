# -*- coding: utf-8 -*-
"""نگهداری ژورنال — append-only و مقاوم به کرش.

قالب هر خط JSON است با یکی از دو نوع:
  {"kind": "signal",  "id": ..., ...}     ← لحظهٔ صدور سیگنال
  {"kind": "outcome", "id": ..., "outcome": "TP|SL|EXPIRED", ...}  ← لحظهٔ بسته‌شدن

رکوردهای قدیمی (مرحله ۳) که ``kind``/``id`` ندارند هم خوانده می‌شوند:
kind پیش‌فرض "signal" و id از ts+symbol ساخته می‌شود.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .. import app_paths

JOURNAL_FILE = "signals.jsonl"

# نتیجه‌ها
TP, SL, EXPIRED = "TP", "SL", "EXPIRED"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Entry:
    """یک سیگنال + (در صورت بسته‌شدن) نتیجهٔ آن."""

    id: str
    ts: datetime
    symbol: str
    direction: str                 # BUY | SELL
    entry: float
    sl: float
    tp: float
    pip: float
    atr: float = 0.0
    risk_pips: float = 0.0
    reward_pips: float = 0.0
    rr: float = 2.0
    score: int = 0
    max_score: int = 11
    session: str = ""
    evidences: list[str] = field(default_factory=list)
    sent: bool = True
    # S4 (v0.27): کلیدِ استراتژی‌های هم‌جهتِ سیگنال — از v0.26 در رکورد
    # journal نوشته می‌شود؛ رکوردهای قدیمی کلید را ندارند → فهرست خالی
    # (صادقانه: در by_strategy شمرده نمی‌شوند، نه حدس زده)
    strategies: list[str] = field(default_factory=list)

    # نتیجه
    outcome: Optional[str] = None          # None = هنوز باز
    outcome_ts: Optional[datetime] = None
    close_price: Optional[float] = None
    r: Optional[float] = None
    note: str = ""

    # ── ویژگی‌ها ────────────────────────────────────────────
    @property
    def is_open(self) -> bool:
        return self.outcome is None

    @property
    def is_win(self) -> bool:
        return self.outcome == TP

    @property
    def is_loss(self) -> bool:
        return self.outcome == SL

    @property
    def risk_price(self) -> float:
        return (self.risk_pips or 0.0) * (self.pip or 0.0001)

    @property
    def week_key(self) -> str:
        y, w, _ = self.ts.isocalendar()
        return f"{y}-W{w:02d}"

    def evidence_keys(self) -> list[str]:
        """کلید مدارکی که امتیاز گرفتند (برای تحلیل همبستگی مدرک↔برد)."""
        out = []
        for e in self.evidences:
            key, _, rest = e.partition(":")
            got, _, _max = rest.partition("/")
            if got and got != "0":
                out.append(key)
        return out


class Journal:
    """دسترسی به فایل ژورنال."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else app_paths.logs_dir() / JOURNAL_FILE

    # ── خواندن ───────────────────────────────────────────────
    def load(self) -> list[Entry]:
        entries: dict[str, Entry] = {}
        order: list[str] = []
        if not self.path.exists():
            return []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue                      # خط خراب نادیده گرفته می‌شود، نه کل فایل
            kind = rec.get("kind", "signal")
            if kind == "signal":
                e = self._entry_from(rec)
                if e.id not in entries:
                    entries[e.id] = e
                    order.append(e.id)
            elif kind == "outcome":
                e = entries.get(rec.get("id", ""))
                if e is not None:
                    self._apply_outcome(e, rec)
        return [entries[i] for i in order]

    @staticmethod
    def _entry_from(rec: dict) -> Entry:
        ts = _parse_dt(rec.get("ts")) or _now()
        sid = rec.get("id") or f"{rec.get('symbol')}-{ts:%Y%m%d%H%M%S}"
        return Entry(
            id=sid, ts=ts,
            symbol=rec.get("symbol", ""), direction=rec.get("direction", ""),
            entry=float(rec.get("entry", 0.0)), sl=float(rec.get("sl", 0.0)),
            tp=float(rec.get("tp", 0.0)), pip=float(rec.get("pip", 0.0001)),
            atr=float(rec.get("atr", 0.0)), risk_pips=float(rec.get("risk_pips", 0.0)),
            reward_pips=float(rec.get("reward_pips", 0.0)), rr=float(rec.get("rr", 2.0)),
            score=int(rec.get("score", 0)), max_score=int(rec.get("max_score", 11)),
            session=rec.get("session", ""), evidences=list(rec.get("evidences") or []),
            sent=bool(rec.get("sent", True)),
            strategies=[str(k) for k in (rec.get("strategies") or [])],
        )

    @staticmethod
    def _apply_outcome(e: Entry, rec: dict) -> None:
        e.outcome = rec.get("outcome")
        e.outcome_ts = _parse_dt(rec.get("ts"))
        e.close_price = rec.get("close_price")
        e.r = rec.get("r")
        e.note = rec.get("note", "")

    # ── نوشتن ───────────────────────────────────────────────
    def append(self, rec: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def add_outcome(self, sid: str, outcome: str, close_price: float,
                    r: float, note: str = "", ts: Optional[datetime] = None) -> None:
        self.append({"kind": "outcome", "id": sid,
                     "ts": (ts or _now()).isoformat(),
                     "outcome": outcome,
                     "close_price": round(close_price, 6) if close_price is not None else None,
                     "r": round(r, 3) if r is not None else None,
                     "note": note})

    # ── پرس‌وجو ──────────────────────────────────────────────
    def open_entries(self) -> list[Entry]:
        return [e for e in self.load() if e.is_open]

    def closed_entries(self) -> list[Entry]:
        return [e for e in self.load() if not e.is_open]


def _parse_dt(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
