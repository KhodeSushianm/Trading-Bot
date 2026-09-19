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


def need_keys(keys, d: dict, where: str) -> None:
    """همهٔ کلیدهای لازم در یک بخش config حاضر باشند."""
    missing = [k for k in keys if k not in d]
    need(not missing, f"{where}: همهٔ زیربخش‌ها حاضرند"
         + (f" (کم دارد: {missing})" if missing else f" ({len(keys)} کلید)"))


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

# ── مرحله ۳: داور امتیازدهی ────────────────────────────────────
j = cfg["judge"]
need_keys(("veto", "risk", "level", "news", "fundamental", "volatility"), j, "judge")
need(isinstance(j.get("enabled"), bool), f"judge.enabled = {j.get('enabled')}")
mx = 11                                    # جمع جدول امتیاز طبق طراحی
need(1 <= int(j.get("min_score", 0)) <= mx,
     f"judge.min_score = {j.get('min_score')} (بین ۱ و {mx})")
need(int(j.get("max_signals_per_cycle", 0)) >= 1,
     f"judge.max_signals_per_cycle = {j.get('max_signals_per_cycle')}")
need(float(j.get("resend_cooldown_minutes", 0)) >= 15,
     f"judge.resend_cooldown_minutes = {j.get('resend_cooldown_minutes')} "
     f"(حداقل ۱۵ = یک چرخه، وگرنه اسپم می‌شود)")
need(int(j.get("resend_score_gain", 0)) >= 1,
     f"judge.resend_score_gain = {j.get('resend_score_gain')}")

v = j["veto"]
for key in ("weekend", "high_impact_event", "timeframe_conflict", "range_market",
            "volatility_spike", "breaking_news"):
    need(isinstance(v.get(key), bool), f"judge.veto.{key} = {v.get(key)}")

r = j["risk"]
need(0 < float(r.get("min_sl_atr", 0)) < float(r.get("sl_atr_multiplier", 0))
     <= float(r.get("max_sl_atr", 0)),
     f"ترتیب آستانه‌های حد ضرر درست است: min={r.get('min_sl_atr')} ≤ "
     f"sl={r.get('sl_atr_multiplier')} ≤ max={r.get('max_sl_atr')}")
need(float(r.get("reward_risk", 0)) >= 1.0,
     f"judge.risk.reward_risk = {r.get('reward_risk')} (زیر ۱ یعنی هدف کوچک‌تر از ریسک!)")
need(float(r.get("level_buffer_atr", -1)) >= 0,
     f"judge.risk.level_buffer_atr = {r.get('level_buffer_atr')}")
need(0 < float(r.get("max_risk_percent", 0)) <= 5,
     f"judge.risk.max_risk_percent = {r.get('max_risk_percent')} (بیش از ۵٪ پرخطر است)")

lv = j["level"]
need(0 < float(lv.get("close_atr", 0)) < float(lv.get("near_atr", 0)),
     f"judge.level: close_atr={lv.get('close_atr')} < near_atr={lv.get('near_atr')}")

vo = j["volatility"]
need(float(vo.get("spike_multiplier", 0)) >= 1.0,
     f"judge.volatility.spike_multiplier = {vo.get('spike_multiplier')} (زیر ۱ = وتوی همیشگی)")
need(int(vo.get("lookback_bars", 0)) >= 20,
     f"judge.volatility.lookback_bars = {vo.get('lookback_bars')} (برای میانگین معتبر)")

jf = j["fundamental"]
need(0 < float(jf.get("clean_med_hours", 0)) < float(jf.get("clean_high_hours", 0)),
     f"judge.fundamental: clean_med_hours={jf.get('clean_med_hours')} < "
     f"clean_high_hours={jf.get('clean_high_hours')}")

jn = j["news"]
need(0 <= int(jn.get("min_score", -1)) <= 6, f"judge.news.min_score = {jn.get('min_score')}")
need(int(jn.get("breaking_min_score", 0)) >= int(jn.get("min_score", 0)),
     "judge.news.breaking_min_score ≥ min_score (وتو باید سخت‌گیرانه‌تر از امتیاز باشد)")

# پنجرهٔ وتوی رویداد باید بین داور و موتور فاندامنتال یکی باشد (یک منبع حقیقت)
need(cfg["judge"]["veto"]["high_impact_event"] is True
     or cfg["fundamental"]["veto_minutes_before"] > 0,
     f"پنجرهٔ وتوی رویداد = {cfg['fundamental']['veto_minutes_before']} دقیقه "
     f"(داور و موتور فاندامنتال از همین یک عدد استفاده می‌کنند)")

# ── مرحله ۴: ژورنال ───────────────────────────────────────────
j = cfg["journal"]
need(isinstance(j.get("enabled"), bool), f"journal.enabled = {j.get('enabled')}")
need(0 < float(j.get("expiry_hours", 0)) <= 24 * 30,
     f"journal.expiry_hours = {j.get('expiry_hours')} (بین ۰ و ۳۰ روز)")
need(isinstance(j.get("conservative_both_touch"), bool),
     f"journal.conservative_both_touch = {j.get('conservative_both_touch')}")
for sect, dflt in (("nightly", "21:30"), ("weekly", "20:00")):
    sp = j[sect]
    need(isinstance(sp.get("enabled"), bool), f"journal.{sect}.enabled = {sp.get('enabled')}")
    hhmm = str(sp.get("time_utc", dflt)).split(":")
    need(len(hhmm) == 2 and hhmm[0].isdigit() and hhmm[1].isdigit()
         and 0 <= int(hhmm[0]) <= 23 and 0 <= int(hhmm[1]) <= 59,
         f"journal.{sect}.time_utc = {sp.get('time_utc')}")
    need(float(sp.get("catchup_window_minutes", 0)) > 0,
         f"journal.{sect}.catchup_window_minutes = {sp.get('catchup_window_minutes')}")
need(0 <= int(j["weekly"].get("day_utc", 0)) <= 6,
     f"journal.weekly.day_utc = {j['weekly'].get('day_utc')} (۰=دوشنبه … ۶=یکشنبه)")

# ── رابط کاربری ───────────────────────────────────────────────
u = cfg.get("ui", {})
need(isinstance(u.get("user_name", ""), str) and len(u.get("user_name", "")) > 0,
     f"ui.user_name = {u.get('user_name')!r} (برای Splash لازم است)")
need(isinstance(u.get("splash", True), bool), f"ui.splash = {u.get('splash')}")
need(isinstance(u.get("animations", True), bool), f"ui.animations = {u.get('animations')}")

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
print(f"✅ config.yaml معتبر است — {len(syms)} نماد، فاندامنتال/اخبار/بریفینگ/داور آماده")
