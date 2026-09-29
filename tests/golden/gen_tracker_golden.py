# -*- coding: utf-8 -*-
"""تولیدکنندهٔ فایل طلاییِ tracker — فاز ۰ (v0.29).

الگوی ریپو («اول میخ، بعد چکش»):
  ۱) این اسکریپت باتریِ ``tests/tracker_scenarios.py`` را روی کدِ *فعلی*
     اجرا و نتیجه را در tests/golden/tracker_golden.json ضبط می‌کند.
  ۲) tests/test_tracker.py همان باتری را تکرار و با طلایی مقایسه می‌کند.
     بعد از سوییچ (فاز ۱/۲) میخ‌ها باید **بدون تغییر** سبز بمانند؛ هر
     بازضبطِ عمدی در CHANGELOG و سندِ معماری مستند می‌شود.

اجرا:  python tests/golden/gen_tracker_golden.py
"""
from __future__ import annotations

import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from tests.tracker_scenarios import battery  # noqa: E402

OUT = _ROOT / "tests" / "golden" / "tracker_golden.json"


def main() -> int:
    data = battery()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                              sort_keys=True) + "\n", encoding="utf-8")
    n_sc = len(data)
    n_res = sum(len(v["resolved_first_call"]) for v in data.values())
    print(f"✅ طلاییِ tracker ضبط شد — {n_sc} سناریو، {n_res} نتیجهٔ بسته‌شده")
    print(f"   → {OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
