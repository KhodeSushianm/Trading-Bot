#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نقطه ورود دستیار سیگنال فارکس — نسخه وب (بدون وابستگی به متاتریدر).

استفاده:
    python main.py                       # تحلیل کامل + تاییدیه تریدینگ‌ویو + گزارش فارسی
    python main.py --source yahoo        # فقط Yahoo (بدون زاپاس)
    python main.py --source twelvedata   # فقط Twelve Data (نیاز به کلید در config.yaml)
    python main.py --config my.yaml      # فایل پیکربندی دیگر
"""
from __future__ import annotations

import argparse
import sys

from src.analysis.strength import currency_strength
from src.analysis.technical import analyze_symbol
from src.config import load_config
from src.data import get_source
from src.data.tradingview import fetch_tv_snapshot
from src.report.console import render_report


def run_once(cfg: dict) -> int:
    """یک چرخه کامل: داده ← تحلیل تکنیکال ← قدرت ارزها ← تاییدیه TV ← گزارش."""
    source = get_source(cfg)
    try:
        source.connect()
    except Exception as e:
        print(f"\n❌ اتصال به منبع داده ناموفق بود:\n   {e}\n")
        return 1

    analyses, datasets, errors = [], {}, 0
    try:
        for sym_cfg in cfg["symbols"]:
            try:
                md = source.fetch(sym_cfg)
                if md is None:
                    errors += 1
                    continue
                datasets[sym_cfg["name"]] = md
                analyses.append(analyze_symbol(sym_cfg, md, cfg["analysis"]))
            except Exception as e:
                errors += 1
                print(f"[!] خطا در تحلیل {sym_cfg['name']}: {e}")
    finally:
        source.disconnect()

    if not analyses:
        print("❌ هیچ نمادی تحلیل نشد — تنظیمات و اتصال اینترنت را بررسی کنید")
        return max(errors, 1)

    ranking = currency_strength(
        datasets, lookback_h1=int(cfg["analysis"].get("strength_lookback_h1", 24))
    )

    # ── تاییدیه تریدینگ‌ویو (اختیاری — در صورت خطا، گزارش بدون آن چاپ می‌شود) ──
    tv_cfg = cfg.get("tradingview") or {}
    tv_map, tv_tf = {}, str(tv_cfg.get("timeframe", "4h"))
    if tv_cfg.get("enabled", True):
        try:
            tv_map = fetch_tv_snapshot(cfg["symbols"], timeframe=tv_tf)
        except Exception as e:
            print(f"[!] تاییدیه تریدینگ‌ویو ناموفق بود: {str(e)[:120]}")

    print(render_report(analyses, ranking, source.name, tv_map=tv_map, tv_tf=tv_tf))
    return 0


def _fix_windows_console() -> None:
    """ویندوز: اطمینان از اینکه کنسول متن فارسی و ایموجی را درست نمایش دهد."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> None:
    _fix_windows_console()
    parser = argparse.ArgumentParser(description="دستیار سیگنال فارکس — موتور تکنیکال + تاییدیه تریدینگ‌ویو")
    parser.add_argument("--config", default=None, help="مسیر فایل پیکربندی YAML")
    parser.add_argument("--source", default=None, choices=["auto", "yahoo", "twelvedata"],
                        help="تغییر موقت منبع داده (بدون ویرایش config)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.source:
        cfg["data_source"] = args.source

    sys.exit(run_once(cfg))


if __name__ == "__main__":
    main()
