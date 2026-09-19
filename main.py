#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حالت خط‌فرمان (بدون پنل گرافیکی) — برای تست و توسعه.

استفاده:
    python main.py                       # یک چرخه تحلیل + گزارش در کنسول
    python main.py --source yahoo        # فقط Yahoo
    python main.py --config my.yaml
برای استفاده روزمره، پنل گرافیکی را اجرا کنید:  python panel.py  (یا EXE)
"""
from __future__ import annotations

import argparse
import sys

from src.config import load_config
from src.engine import run_cycle


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
    parser = argparse.ArgumentParser(description="دستیار سیگنال فارکس — حالت خط‌فرمان")
    parser.add_argument("--config", default=None, help="مسیر فایل پیکربندی YAML")
    parser.add_argument("--source", default=None, choices=["auto", "yahoo", "twelvedata"],
                        help="تغییر موقت منبع داده (بدون ویرایش config)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.source:
        cfg["data_source"] = args.source

    res = run_cycle(cfg, on_log=lambda m: print(m, file=sys.stderr))
    if res["report"]:
        print(res["report"])
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
