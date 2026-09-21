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
    check(data["device_id"] == did and data["version"] == "2.0", "device_id کامل قفل شد")

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

print("=" * 70)
if FAILS:
    print(f"❌ {len(FAILS)} تست شکست خورد:")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("✅ همهٔ تست‌های لایسنس پاس شد")
sys.exit(0)
