#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نقطه ورود دستیار سیگنال فارکس.

استفاده:
    python main.py                # یک تحلیل کامل و چاپ گزارش (مرحله ۱)
    python main.py --config my.yaml
    python main.py --source mt5   # overriding منبع داده بدون ویرایش config
"""
from __future__ import annotations

import argparse
import sys

from src.analysis.strength import currency_strength
from src.analysis.technical import analyze_symbol
from src.config import load_config
from src.data import get_source
from src.report.console import render_report


def run_once(cfg: dict) -> int:
    """یک چرخه کامل: داده ← تحلیل تکنیکال ← قدرت ارزها ← گزارش. کد خروج = تعداد خطاها."""
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
        print("❌ هیچ نمادی تحلیل نشد — تنظیمات و اتصال را بررسی کنید")
        return max(errors, 1)

    ranking = currency_strength(
        datasets, lookback_h1=int(cfg["analysis"].get("strength_lookback_h1", 24))
    )
    print(render_report(analyses, ranking, source.name))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="دستیار سیگنال فارکس — موتور تکنیکال")
    parser.add_argument("--config", default=None, help="مسیر فایل پیکربندی YAML")
    parser.add_argument("--source", default=None, choices=["mt5", "yahoo"],
                        help="تغییر موقت منبع داده (بدون ویرایش config)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.source:
        cfg["data_source"] = args.source

    sys.exit(run_once(cfg))


if __name__ == "__main__":
    main()
