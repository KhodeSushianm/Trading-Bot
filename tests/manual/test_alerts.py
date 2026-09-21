# -*- coding: utf-8 -*-
"""تست هشدارهای قیمت دسکتاپ (v0.19.0) — src/alerts.py همزاد js/alerts.js.

اجرا: python tests/manual/test_alerts.py
"""
import os
import pathlib
import sys
import tempfile
from datetime import datetime, timedelta, timezone

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


with tempfile.TemporaryDirectory() as td:
    os.environ["ODIN_DATA_DIR"] = td
    from src import alerts as A

    print("=" * 70)
    print("۱) افزودن/تکراری/سقف/نامعتبر")
    print("=" * 70)
    ok, why = A.add_alert("EURUSD", "above", 1.18, pip=0.0001)
    check(ok, "افزودن هشدار بالا")
    ok, why = A.add_alert("EURUSD", "above", 1.18)
    check(not ok and why == "duplicate", "تکراری رد می‌شود")
    ok, why = A.add_alert("EURUSD", "below", 1.18)
    check(ok, "همان قیمت، جهت دیگر = هشدار جدا")
    ok, why = A.add_alert("EURUSD", "above", 0)
    check(not ok and why == "invalid", "قیمت صفر رد می‌شود")
    check(A.alert_id("EURUSD", "above", 1.18) == "EURUSD|above|1.18", "id یکتا")
    for i in range(18):
        A.add_alert("XAUUSD", "above", 3000 + i, pip=1)
    ok, why = A.add_alert("XAUUSD", "above", 9999)
    check(not ok and why == "max", f"سقف {A.MAX_ALERTS} هشدار")

    print("=" * 70)
    print("۲) عبور قیمت — یک‌بارمصرف و چسبنده")
    print("=" * 70)
    # پاک‌سازی و چیدمان سناریو
    for r in list(A.load_alerts()):
        A.remove_alert(r["id"])
    A.add_alert("EURUSD", "above", 1.18, pip=0.0001)                       # یک‌بار A
    A.add_alert("EURUSD", "below", 1.10, pip=0.0001)                       # یک‌بار B
    A.add_alert("EURUSD", "above", 1.15, sticky=True, pip=0.0001)          # چسبنده C
    an = [{"symbol": "EURUSD", "price": 1.17, "pip": 0.0001}]
    fired = A.check_alerts(an)
    check(len(fired) == 1 and fired[0]["id"].endswith("|above|1.15"),
          "فقط چسبنده (1.17≥1.15) فعال می‌شود")
    check(len(A.load_alerts()) == 3, "چسبنده حذف نمی‌شود")
    t0 = datetime.now(timezone.utc)
    fired = A.check_alerts(an, now=t0 + timedelta(minutes=1))
    check(len(fired) == 0, "کول‌داون ۶۰ دقیقه‌ای چسبنده")
    fired = A.check_alerts(an, now=t0 + timedelta(minutes=61))
    check(len(fired) == 1, "چسبنده بعد از کول‌داون دوباره فعال می‌شود")
    fired = A.check_alerts([{"symbol": "EURUSD", "price": 1.185, "pip": 0.0001}],
                           now=t0 + timedelta(minutes=62))
    ids = {f["id"] for f in fired}
    check(any(i.endswith("|above|1.18") for i in ids), "A با عبور به بالا فعال شد")
    rows = A.load_alerts()
    check(all(not r["id"].endswith("|above|1.18") for r in rows), "یک‌بارمصرف پس از شلیک حذف شد")
    fired = A.check_alerts([{"symbol": "EURUSD", "price": 1.095, "pip": 0.0001}],
                           now=t0 + timedelta(minutes=63))
    check(any(f["id"].endswith("|below|1.1") for f in fired), "B با عبور به پایین فعال شد")
    rows = A.load_alerts()
    check(len(rows) == 1 and rows[0]["sticky"], "فقط چسبنده باقی می‌ماند")
    check(fired[0].get("_price") == 1.095, "قیمت لحظهٔ شلیک در رکورد هست")

    print("=" * 70)
    print("۳) نبودِ نماد / دادهٔ خراب / حذف دستی")
    print("=" * 70)
    fired = A.check_alerts([{"symbol": "USDJPY", "price": 147.0, "pip": 0.01}])
    check(fired == [], "نمادِ نامرتبط → شلیک نمی‌شود")
    check(len(A.load_alerts()) == 1, "رکورد دست‌نخورده ماند")
    A.remove_alert(rows[0]["id"])
    check(A.load_alerts() == [], "حذف دستی")
    (pathlib.Path(td) / "alerts.json").write_text("{{{bad", encoding="utf-8")
    check(A.load_alerts() == [], "JSON خراب → فهرست خالی، بدون کرش")

print("=" * 70)
if FAILS:
    print(f"❌ {len(FAILS)} خطا:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ تست‌های هشدار قیمت پاس شد")
sys.exit(0)
