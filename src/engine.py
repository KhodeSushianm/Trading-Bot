# -*- coding: utf-8 -*-
"""موتور ربات — مستقل از رابط کاربری.

- run_cycle(): یک چرخه کامل (داده ← تحلیل ← تاییدیه TV ← گزارش ← تلگرام ← لاگ فایل)
- BotLoop():   حلقه زمان‌بندی‌شده در thread پس‌زمینه (هر interval_minutes)

هم پنل گرافیکی و هم main.py (خط فرمان) از همین موتور استفاده می‌کنند.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

from . import app_paths
from .analysis.strength import currency_strength
from .analysis.technical import analyze_symbol
from .config import load_config
from .data import get_source
from .data.tradingview import fetch_tv_snapshot
from .notify import telegram
from .report.console import render_report

LogFn = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def run_cycle(cfg: Optional[dict] = None, on_log: LogFn = _noop) -> dict:
    """یک چرخه کامل تحلیل.

    Returns:
        dict با کلیدهای: ok, report, errors, telegram=(bool,msg), elapsed
    """
    t0 = time.time()
    cfg = cfg or load_config()
    result = {"ok": False, "report": "", "errors": 0, "telegram": (False, ""), "elapsed": 0.0}

    def log(msg: str) -> None:
        on_log(f"[{datetime.now():%H:%M:%S}] {msg}")

    try:
        source = get_source(cfg)
        source.connect()
    except Exception as e:
        log(f"❌ اتصال به منبع داده ناموفق: {str(e)[:120]}")
        result["errors"] = 1
        return result

    analyses, datasets, errors = [], {}, 0
    try:
        total = len(cfg["symbols"])
        for i, sym_cfg in enumerate(cfg["symbols"], 1):
            if total > 1:
                log(f"📡 دریافت و تحلیل {sym_cfg['name']} ({i}/{total})...")
            try:
                md = source.fetch(sym_cfg)
                if md is None:
                    errors += 1
                    continue
                datasets[sym_cfg["name"]] = md
                analyses.append(analyze_symbol(sym_cfg, md, cfg["analysis"]))
            except Exception as e:
                errors += 1
                log(f"[!] خطا در {sym_cfg['name']}: {str(e)[:100]}")
    finally:
        source.disconnect()

    if not analyses:
        log("❌ هیچ نمادی تحلیل نشد — اینترنت/تنظیمات را بررسی کنید")
        result["errors"] = max(errors, 1)
        return result

    log(f"✅ تحلیل {len(analyses)} نماد انجام شد")
    ranking = currency_strength(
        datasets, lookback_h1=int(cfg["analysis"].get("strength_lookback_h1", 24))
    )

    # تاییدیه تریدینگ‌ویو (اختیاری — در صورت خطا گزارش بدون آن ساخته می‌شود)
    tv_cfg = cfg.get("tradingview") or {}
    tv_map, tv_tf = {}, str(tv_cfg.get("timeframe", "4h"))
    if tv_cfg.get("enabled", True):
        log("🔍 دریافت تاییدیه تریدینگ‌ویو...")
        try:
            tv_map = fetch_tv_snapshot(cfg["symbols"], timeframe=tv_tf)
            log(f"✅ تاییدیه تریدینگ‌ویو برای {len(tv_map)} نماد دریافت شد")
        except Exception as e:
            log(f"[!] تاییدیه تریدینگ‌ویو ناموفق: {str(e)[:90]}")

    report = render_report(analyses, ranking, source.name, tv_map=tv_map, tv_tf=tv_tf)
    result.update(report=report, errors=errors, ok=True)

    # بایگانی گزارش‌ها در فایل (برای مرور بعدی)
    try:
        with open(app_paths.logs_dir() / "reports.log", "a", encoding="utf-8") as f:
            f.write(f"\n\n{'#' * 70}\n# {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC\n"
                    f"{'#' * 70}\n{report}\n")
    except Exception:
        pass

    # ارسال به تلگرام
    tg = cfg.get("telegram") or {}
    token = str(tg.get("bot_token") or "").strip()
    chat_id = str(tg.get("chat_id") or "").strip()
    if tg.get("send_reports", True) and token and chat_id:
        log("📱 ارسال گزارش به تلگرام...")
        ok, msg = telegram.send_message(token, chat_id, report)
        result["telegram"] = (ok, msg)
        log(("✅ " if ok else "❌ ") + f"تلگرام: {msg}")
    else:
        log("[i] تلگرام تنظیم نشده — گزارش فقط در پنل/کنسول نمایش داده می‌شود")

    result["elapsed"] = time.time() - t0
    log(f"🏁 چرخه تحلیل کامل شد ({result['elapsed']:.0f} ثانیه)")
    return result


class BotLoop:
    """حلقه زمان‌بندی‌شده در thread پس‌زمینه (با قابلیت توقف امن)."""

    def __init__(self, on_log: LogFn = _noop,
                 on_report: Callable[[str], None] = lambda _: None,
                 cfg_provider: Callable[[], dict] = load_config):
        self.on_log = on_log
        self.on_report = on_report
        self.cfg_provider = cfg_provider
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.interval_min = 15.0
        self.state: dict = {"last_run": None, "next_run": None,
                            "cycles": 0, "last_error": None}

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="bot-loop")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=6)
        self._thread = None
        self.state["next_run"] = None
        self.on_log("⏹ ربات متوقف شد")

    def run_once_async(self) -> bool:
        """یک چرخه فوری در thread جدا (دکمه «اجرای یک‌بار»). اگر مشغول باشد False."""
        if self._once_running:
            return False
        threading.Thread(target=self._once, daemon=True, name="bot-once").start()
        return True

    _once_running = False

    def _once(self) -> None:
        self._once_running = True
        try:
            res = run_cycle(self.cfg_provider(), on_log=self.on_log)
            if res.get("report"):
                self.on_report(res["report"])
            self.state["last_run"] = time.time()
            self.state["cycles"] += 1
        finally:
            self._once_running = False

    # ── حلقه اصلی ─────────────────────────────────────────────
    def _run(self) -> None:
        self.on_log("▶ ربات شروع به کار کرد — تحلیل خودکار فعال است")
        while not self._stop.is_set():
            try:
                cfg = self.cfg_provider()   # تنظیمات تازه هر چرخه (تغییرات پنل بدون ری‌استارت)
                self.interval_min = float((cfg.get("loop") or {}).get("interval_minutes", 15))
                res = run_cycle(cfg, on_log=self.on_log)
                if res.get("report"):
                    self.on_report(res["report"])
                if not res.get("ok"):
                    self.state["last_error"] = "آخرین چرخه ناموفق بود"
                else:
                    self.state["last_error"] = None
            except Exception as e:
                self.on_log(f"❌ خطای غیرمنتظره: {str(e)[:130]}")
                self.state["last_error"] = str(e)[:130]
            self.state["last_run"] = time.time()
            self.state["next_run"] = time.time() + self.interval_min * 60
            self.state["cycles"] += 1
            if self._stop.wait(self.interval_min * 60):
                break
        self.on_log("⏹ ربات متوقف شد")
