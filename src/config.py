# -*- coding: utf-8 -*-
"""بارگذاری و اعتبارسنجی فایل پیکربندی."""
import os

import yaml

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")


def load_config(path: str | None = None) -> dict:
    """فایل YAML را می‌خواند و کلیدهای ضروری را بررسی می‌کند."""
    path = path or DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"فایل پیکربندی پیدا نشد: {path}")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    for key in ("data_source", "symbols", "analysis"):
        if key not in cfg:
            raise ValueError(f"کلید الزامی «{key}» در config.yaml وجود ندارد")
    if not isinstance(cfg["symbols"], list) or not cfg["symbols"]:
        raise ValueError("«symbols» باید فهرستی غیرخالی از نمادها باشد")
    for sym in cfg["symbols"]:
        for field in ("name", "base", "quote", "pip"):
            if field not in sym:
                raise ValueError(f"نماد {sym.get('name', '?')} فیلد «{field}» ندارد")
    cfg.setdefault("history", {})
    cfg.setdefault("twelvedata", {})
    cfg.setdefault("tradingview", {})
    return cfg
