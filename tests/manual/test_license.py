# -*- coding: utf-8 -*-
"""تست کامل سیستم لایسنس (v0.14.0) — طرح HMAC + قفل دستگاه + چرخهٔ فعال‌سازی.

آفلاین و قطعی؛ روی هر سه پلتفرم. ذخیره‌سازی با ODIN_DATA_DIR موقت ایزوله می‌شود
تا به دادهٔ واقعی کاربر دست نزند.

اجرا: python tests/manual/test_license.py
"""
import json
import os
import pathlib
import sys
import tempfile

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


with tempfile.TemporaryDirectory() as td:
    os.environ["ODIN_DATA_DIR"] = td          # ایزوله‌سازی license.dat
    os.environ.pop("ODIN_SKIP_LICENSE", None)

    from src import license as lic

    print("=" * 70)
    print("۱) شناسه و کد دستگاه")
    print("=" * 70)
    did = lic.get_device_id()
    check(len(did) == 64 and all(c in "0123456789abcdef" for c in did),
          "device_id = ۶۴ هگز کوچک")
    check(did == lic.get_device_id(), "device_id قطعی است (دو فراخوانی یکی)")
    code = lic.get_device_code(did)
    check(code == f"{did[:12].upper()[:4]}-{did[:12].upper()[4:8]}-{did[:12].upper()[8:12]}",
          f"device_code از ۱۲ رقم اول ساخته می‌شود: {code}")
    check(lic.normalize_code(" ab12-cd34 ef56 ") == "AB12CD34EF56", "normalize_code مقاوم است")

    print("=" * 70)
    print("۲) تولید و اعتبارسنجی کلید (HMAC)")
    print("=" * 70)
    key = lic.generate_license_key(code)
    check(len(key) == 19 and key.count("-") == 3, f"کلید ۴ گروه ۴تایی است: {key}")
    check(key == lic.generate_license_key(code), "کلید قطعی است")
    ok, _ = lic.validate_license(key)
    check(ok, "کلیدِ دستگاهِ فعلی معتبر است")
    ok, _ = lic.validate_license(key.lower().replace("-", " "))
    check(ok, "اعتبارسنجی به فاصله/کوچک‌بزرگی مقاوم است")
    ok, msg = lic.validate_license("AAAA-BBBB-CCCC-DDDD")
    check(not ok, "کلید تصادفی رد می‌شود")
    ok, msg = lic.validate_license("short")
    check(not ok, "رشتهٔ کوتاه رد می‌شود")
    ok, msg = lic.validate_license(key, "FF00-FF00-FF00")
    check(not ok, "کلیدِ دستگاهِ دیگر روی این دستگاه رد می‌شود")
    # بُرِد مشترک پایتون/JS (secret یکسان) — js/license.js باید همین را بدهد
    check(lic.generate_license_key("AB12CD34EF56") == "6F1F-8540-078F-9898",
          "بُرِد آزمایشی مشترک با JS")

    print("=" * 70)
    print("۳) چرخهٔ فعال‌سازی (save/load/enforce/deactivate)")
    print("=" * 70)
    check(not lic.is_activated(), "ماشین تازه: فعال نیست")
    ok, msg = lic.check_and_enforce_license()
    check(not ok, "دروازهٔ اجرا بدون لایسنس بسته است")

    ok, msg = lic.activate_program("AAAA-BBBB-CCCC-DDDD", "کاربر تست")
    check(not ok, "فعال‌سازی با کلید غلط رد می‌شود")
    ok, msg = lic.activate_program(key, "کاربر تست")
    check(ok, "فعال‌سازی با کلید درست موفق است")
    check(lic.is_activated(), "پس از فعال‌سازی، is_activated=True")
    ok, msg = lic.check_and_enforce_license()
    check(ok, "دروازهٔ اجرا باز شد")

    lf = lic.get_license_file_path()
    check(lf.exists(), "license.dat ساخته شد")
    data = json.loads(lf.read_text(encoding="utf-8"))
    check(data["device_id"] == did and data["version"] == "2.1", "device_id کامل قفل شد (نسخهٔ رکورد 2.1)")

    # کپی license.dat روی «دستگاه دیگر» نباید کار کند
    saved = dict(data)
    saved["device_id"] = "0" * 64
    lf.write_text(json.dumps(saved), encoding="utf-8")
    check(not lic.is_activated(), "license.dat با device_id بیگانه رد می‌شود (ضدکپی)")
    lf.write_text(json.dumps(data), encoding="utf-8")

    # bypass توسعه/CI
    os.environ["ODIN_SKIP_LICENSE"] = "1"
    check(lic.license_bypassed(), "ODIN_SKIP_LICENSE=1 → bypass")
    os.environ.pop("ODIN_SKIP_LICENSE")

    check(lic.deactivate_program(), "غیرفعال‌سازی موفق")
    check(not lf.exists() and not lic.is_activated(), "پس از غیرفعال‌سازی: فایل حذف و قفل بسته")

    print("=" * 70)
    print("۴) CLI سازنده")
    print("=" * 70)
    check(lic._cli(["gen", "AB12-CD34-EF56"]) == 0, "gen با کد درست → خروج ۰")
    check(lic._cli(["check", "6F1F-8540-078F-9898", "AB12CD34EF56"]) == 0, "check کلید درست → ۰")
    check(lic._cli(["check", "AAAA-BBBB-CCCC-DDDD", "AB12CD34EF56"]) == 1, "check کلید غلط → ۱")
    check(lic._cli(["gen", "xyz"]) == 2, "gen با کد نامعتبر → ۲")
    check(lic._cli(["gen", "AB12-CD34-EF56", "--until", "2030-12-31"]) == 0, "gen --until → ۰")
    check(lic._cli(["gen", "AB12-CD34-EF56", "--days", "30"]) == 0, "gen --days → ۰")

    print("=" * 70)
    print("۵) کلید زمان‌دار (v0.15.0)")
    print("=" * 70)
    from datetime import datetime, timedelta
    kt = lic.generate_license_key("AB12-CD34-EF56", until="2030-12-31")
    check(kt == "19DB-2DFA-F0E7-0082-301231", f"بُرِد مشترک زمان‌دار با JS: {kt}")
    key16, exp8 = lic.parse_key_input(kt)
    check(exp8 == "20301231" and len(key16) == 16, "پارس پسوند تاریخ")
    check(lic.validate_license(kt, "AB12-CD34-EF56")[0], "کلید زمان‌دار معتبر است")
    check(not lic.validate_license(kt, "AB12-CD34-EF56", now=datetime(2031, 1, 1))[0],
          "پس از انقضا رد می‌شود")
    check(not lic.validate_license("19DB-2DFA-F0E7-0082", "AB12-CD34-EF56")[0],
          "حذف پسوند تاریخ → رد (HMAC روی تاریخ هم هست)")
    try:
        lic.parse_key_input("19DB2DFAF0E70082-310231")
        check(False, "۳۱ فوریه باید رد شود")
    except ValueError:
        check(True, "تاریخ نامعتبر (۳۱ فوریه) رد می‌شود")
    kd = lic.generate_license_key(code, 90)
    _, e90 = lic.parse_key_input(kd)
    delta = (datetime.strptime(e90, "%Y%m%d").date() - datetime.now().date()).days
    check(delta in (89, 90), f"--days 90 → انقضا ~۹۰ روز (={delta})")

    print("=" * 70)
    print("۶) دورهٔ آزمایشی ۷ روزه + ضدِ ساعت")
    print("=" * 70)
    t0 = lic.trial_status()
    check(not t0["exists"] and not t0["active"], "تریال شروع نشده")
    ok, _m = lic.check_and_enforce_license()
    check(not ok, "بدون لایسنس/تریال → دروازه بسته")
    check(lic.start_trial()[0], "start_trial موفق")
    check(not lic.start_trial()[0], "start_trial دوباره → رد (ضدتقلب)")
    t1 = lic.trial_status()
    check(t1["active"] and t1["days_left"] == 7, "روز ۰ → فعال، ۷ روز باقی")
    ok, msg = lic.check_and_enforce_license()
    check(ok and "آزمایشی" in msg, "دروازه با تریال باز است")
    t2 = lic.trial_status(now=datetime.now() + timedelta(days=6, hours=12))
    check(t2["active"] and t2["days_left"] == 1, "روز ۶.۵ → ۱ روز باقی")
    t3 = lic.trial_status(now=datetime.now() + timedelta(days=7, hours=3))
    check(not t3["active"] and t3["days_left"] == 0, "روز ۷.۱ → تمام")
    t4 = lic.trial_status(now=datetime.now() - timedelta(hours=96))
    check(t4["tampered"] and not t4["active"], "عقب‌کشیدن ساعت → tampered")
    kdev = lic.generate_license_key(code, until="2030-12-31")
    ok, msg = lic.activate_program(kdev, "تستر")
    check(ok, "فعال‌سازی با کلید زمان‌دار")
    check(lic.is_activated(), "is_activated با کلید زمان‌دار")
    check(not lic.is_activated(now=datetime(2031, 1, 2)), "is_activated پس از انقضا → False")
    data = json.loads(lic.get_license_file_path().read_text(encoding="utf-8"))
    check(data.get("expires_at") == "20301231" and data.get("version") == "2.1",
          "expires_at/version در license.dat ذخیره شد")

print("=" * 70)
if FAILS:
    print(f"❌ {len(FAILS)} تست شکست خورد:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ تست‌های لایسنس پاس شد")
sys.exit(0)
