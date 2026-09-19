#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اعتبارسنجی config.yaml — بدون اینترنت، بدون GUI.

در CI اجرا می‌شود تا اگر کلیدی از قلم افتاد یا مقدار نامعتبری نوشته شد،
قبل از ساخت EXE جلویش گرفته شود.

    python tests/check_config.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config  # noqa: E402

REQUIRED_SYMBOL_FIELDS = ("name", "fa", "yahoo", "base", "quote", "pip")
errors: list[str] = []


def need(cond: bool, msg: str) -> None:
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        errors.append(msg)


cfg = load_config()

print("─" * 62)
print("اعتبارسنجی config.yaml")
print("─" * 62)

# ── نمادها ────────────────────────────────────────────────────
syms = cfg["symbols"]
need(isinstance(syms, list) and len(syms) >= 1, f"نمادها: {len(syms)} مورد")
names = [s.get("name") for s in syms]
need(len(set(names)) == len(names), f"نام نمادها یکتاست: {names}")
for s in syms:
    missing = [f for f in REQUIRED_SYMBOL_FIELDS if f not in s]
    need(not missing, f"{s.get('name')}: فیلدهای کامل" + (f" (کم دارد: {missing})" if missing else ""))
    need(s.get("base") != s.get("quote"), f"{s.get('name')}: ارز پایه و مظنه متفاوت‌اند")
    need(float(s.get("pip", 0)) > 0, f"{s.get('name')}: pip معتبر ({s.get('pip')})")

# ── منبع داده ─────────────────────────────────────────────────
need(cfg["data_source"] in ("auto", "yahoo", "twelvedata"),
     f"data_source معتبر: {cfg['data_source']}")

# ── تحلیل تکنیکال ─────────────────────────────────────────────
a = cfg["analysis"]
need(a["ema_fast"] < a["ema_slow"], f"EMA سریع ({a['ema_fast']}) < کند ({a['ema_slow']})")
need(0 < a["adx_min_trend"] < 100, f"آستانهٔ ADX معتبر: {a['adx_min_trend']}")

# ── مرحله ۲: فاندامنتال ───────────────────────────────────────
f = cfg["fundamental"]
need(isinstance(f.get("enabled"), bool), f"fundamental.enabled = {f.get('enabled')}")
need(str(f.get("source_url", "")).startswith("https://"), "fundamental.source_url یک آدرس HTTPS است")
need(float(f.get("cache_ttl_minutes", 0)) > 0, f"cache_ttl_minutes = {f.get('cache_ttl_minutes')}")
need(float(f.get("horizon_hours", 0)) > 0, f"horizon_hours = {f.get('horizon_hours')}")
need(0 < float(f.get("veto_minutes_before", 0)) <= 240,
     f"veto_minutes_before = {f.get('veto_minutes_before')} (بین ۰ و ۲۴۰)")
need(0 < float(f.get("alert_before_minutes", 0)) <= 240,
     f"alert_before_minutes = {f.get('alert_before_minutes')}")
need(float(f.get("alert_grace_minutes", 0)) >= 0,
     f"alert_grace_minutes = {f.get('alert_grace_minutes')}")

# ── مرحله ۲: اخبار ────────────────────────────────────────────
n = cfg["news"]
need(isinstance(n.get("enabled"), bool), f"news.enabled = {n.get('enabled')}")
need(0 < float(n.get("max_age_hours", 0)) <= 168, f"news.max_age_hours = {n.get('max_age_hours')}")
need(0 <= int(n.get("min_score", -1)) <= 6, f"news.min_score = {n.get('min_score')} (بین ۰ و ۶)")
need(int(n.get("max_total", 0)) > 0, f"news.max_total = {n.get('max_total')}")
need(int(n.get("max_items_per_feed", 0)) > 0,
     f"news.max_items_per_feed = {n.get('max_items_per_feed')}")

# ── مرحله ۲: بریفینگ ──────────────────────────────────────────
b = cfg["briefing"]
need(isinstance(b.get("enabled"), bool), f"briefing.enabled = {b.get('enabled')}")
need(isinstance(b.get("times_utc"), list) and bool(b["times_utc"]),
     f"briefing.times_utc فهرست غیرخالی است: {b.get('times_utc')}")
for t in b.get("times_utc", []):
    parts = str(t).split(":")
    ok = (len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()
          and 0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59)
    need(ok, f"ساعت معتبر: {t}")
need(float(b.get("horizon_hours", 0)) > 0, f"briefing.horizon_hours = {b.get('horizon_hours')}")
need(float(b.get("catchup_window_minutes", 0)) > 0,
     f"briefing.catchup_window_minutes = {b.get('catchup_window_minutes')}")

# ── تلگرام و حلقه ─────────────────────────────────────────────
tg = cfg["telegram"]
need("bot_token" in tg and "chat_id" in tg, "کلیدهای تلگرام موجود است")
need(not str(tg.get("bot_token", "")).strip(),
     "config.yaml حاوی توکن تلگرام نیست (باید در config.local.yaml باشد) 🔒")
need(float(cfg["loop"]["interval_minutes"]) >= 1,
     f"loop.interval_minutes = {cfg['loop']['interval_minutes']}")

print("─" * 62)
if errors:
    print(f"❌ {len(errors)} مشکل در config.yaml:")
    for e in errors:
        print("   -", e)
    sys.exit(1)
print(f"✅ config.yaml معتبر است — {len(syms)} نماد، موتور فاندامنتال/اخبار/بریفینگ آماده")
