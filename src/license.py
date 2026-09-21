#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سیستم لایسنس و قفل دستگاه برای ODIN Assistant (v0.14.0 — طرح HMAC).

طرح (یکسان در دسکتاپ و اندروید، پس یک ابزار تولید کلید برای هر دو کافی است):

  ۱) شناسهٔ دستگاه (device_id)  = SHA-256 از پایدارترین شناسه‌های سیستم
     (ویندوز: MachineGuid · لینوکس: machine-id · مک: IOPlatformUUID ·
      اندروید: ANDROID_ID — سمت Bridge). فقط وقتی هیچ‌کدام نبود، MAC.
  ۲) کد دستگاه (device_code)    = ۱۲ رقم اولِ هگزِ device_id، بالا‌حروف،
     با جداکننده: «XXXX-XXXX-XXXX». کاربر همین را برای سازنده می‌فرستد.
  ۳) کلید لایسنس                = HMAC-SHA256(SECRET, device_code) →
     ۱۶ رقم هگز بالا‌حروف → «XXXX-XXXX-XXXX-XXXX».
  ۴) اعتبارسنجی در اپ: HMAC دوباره از کد دستگاهِ فعلی ساخته و با
     compare_digest مقایسه می‌شود؛ سپس device_id کامل در license.dat
     قفل می‌شود (کپی فایل لایسنس روی دستگاه دیگر کار نمی‌کند).

صداقت اول: این طرح «آفلاین و بدون سرور» است و secret داخل بستهٔ برنامه
قرار دارد؛ جلوی کپی/اشتراک غیرمجاز روزمره را می‌گیرد اما در برابر کرکرِ
حرفه‌ای (استخراج secret از باینری) مصون نیست — این محدودیتِ ذاتیِ هر
لایسنس آفلاین است و در LICENSE_GUIDE.md مستند شده.

CLI (سمت سازنده):
    python -m src.license device          # شناسه/کد دستگاهِ همین ماشین
    python -m src.license gen CODE        # تولید کلید برای کد دستگاه مشتری
    python -m src.license check KEY CODE  # راستی‌آزمایی کلید
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

from src import app_paths

# ══════════════════════════════════════════════════════════════
#  ثابت‌های طرح
# ══════════════════════════════════════════════════════════════
# ⚠️ همین مقدار در android/app/src/main/assets/www/js/license.js هم هست.
# تغییر آن = باطل‌شدن همهٔ کلیدهای صادرشده (هر دو فایل با هم عوض شوند).
_LICENSE_SECRET = "bd604d7cc90e8fe32184e8d6ddb5787c3389438b54156947541f772f61be7347"

_HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")


# ══════════════════════════════════════════════════════════════
#  شناسهٔ دستگاه
# ══════════════════════════════════════════════════════════════
def _first_existing(paths: list[str]) -> str | None:
    for p in paths:
        try:
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    v = f.read().strip()
                if v:
                    return v
        except Exception:
            continue
    return None


def _mac_fallback() -> str:
    """MAC از uuid.getnode — آخرین چاره (روی VPN/چند-NIC ممکن است عوض شود)."""
    return ":".join(f"{(uuid.getnode() >> i) & 0xFF:02x}" for i in range(40, -8, -8))


def _stable_hardware_id() -> str:
    """پایدارترین شناسهٔ هر پلتفرم — بدون وابستگی بیرونی."""
    system = platform.system()
    if system == "Linux":
        v = _first_existing(["/etc/machine-id", "/var/lib/dbus/machine-id"])
        if v:
            return f"linux-machine-id:{v}"
    elif system == "Windows":
        # MachineGuid — کلید ماشین، پایدار بین ریستارت‌ها و نصب مجدد ویندوز.
        # (wmic در بیلدهای تازهٔ ویندوز ۱۱ حذف شده؛ winreg همیشه هست.)
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Cryptography") as k:
                guid, _ = winreg.QueryValueEx(k, "MachineGuid")
            if guid:
                return f"win-machineguid:{guid}"
        except Exception:
            pass
        try:  # زاپاس: UUID بایوس از PowerShell (اگر ویندوز بلاک نکند)
            import subprocess
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"],
                capture_output=True, text=True, timeout=15)
            uid = (r.stdout or "").strip().splitlines()[-1].strip() if r.stdout else ""
            if uid and uid.lower() not in ("", "ffffffff-ffff-ffff-ffff-ffffffffffff"):
                return f"win-csuuid:{uid}"
        except Exception:
            pass
    elif system == "Darwin":
        try:
            import subprocess
            r = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                               capture_output=True, text=True, timeout=15)
            for line in (r.stdout or "").split("\n"):
                if "IOPlatformUUID" in line:
                    uid = line.split("=")[-1].strip().strip('"')
                    if uid:
                        return f"mac-uuid:{uid}"
        except Exception:
            pass
    return f"mac:{_mac_fallback()}"


def get_device_id() -> str:
    """SHA-256 هگز (۶۴ کاراکتر) از شناسهٔ پایدار دستگاه."""
    return hashlib.sha256(_stable_hardware_id().encode("utf-8")).hexdigest()


def format_code(raw: str) -> str:
    """«AB12CD34EF56» → «AB12-CD34-EF56» (جداسازی ۴تایی)."""
    return "-".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def get_device_code(device_id: str | None = None) -> str:
    """کد ۱۲ کاراکتری که کاربر به سازنده می‌دهد (با جداکننده)."""
    did = (device_id or get_device_id())[:12].upper()
    return format_code(did)


def normalize_code(code: str) -> str:
    """«ab12-cd34-ef56»/«AB12 CD34EF56» → «AB12CD34EF56»."""
    return re.sub(r"[^0-9A-Fa-f]", "", str(code or "")).upper()


# ══════════════════════════════════════════════════════════════
#  کلید لایسنس (HMAC)
# ══════════════════════════════════════════════════════════════
def _hmac_key_hex(device_code: str) -> str:
    code = normalize_code(device_code)
    if len(code) != 12 or not _HEX_RE.match(code):
        raise ValueError("device_code must be 12 hex chars")
    return hmac.new(_LICENSE_SECRET.encode("utf-8"), code.encode("utf-8"),
                    hashlib.sha256).hexdigest().upper()[:16]


def generate_license_key(device_code: str) -> str:
    """تولید کلید برای یک کد دستگاه — ابزار سمت سازنده.

    خروجی: «XXXX-XXXX-XXXX-XXXX» — همان چیزی که مشتری وارد می‌کند.
    """
    return format_code(_hmac_key_hex(device_code))


def validate_license(license_key: str, device_code: str | None = None) -> tuple[bool, str]:
    """اعتبارسنجی کلید در برابر کد دستگاه (پیش‌فرض: دستگاه فعلی)."""
    key = re.sub(r"[^0-9A-Fa-f]", "", str(license_key or "")).upper()
    if len(key) != 16 or not _HEX_RE.match(key):
        return False, "فرمت کلید نادرست است (باید ۱۶ رقم هگز باشد: XXXX-XXXX-XXXX-XXXX)"
    try:
        expected = _hmac_key_hex(device_code or get_device_code())
    except ValueError:
        return False, "شناسهٔ دستگاه نامعتبر است"
    if hmac.compare_digest(key, expected):
        return True, "لایسنس معتبر است"
    return False, "این کلید برای دستگاه دیگری ساخته شده — کد دستگاه را برای سازنده بفرستید و کلید همان دستگاه را بگیرید"


# ══════════════════════════════════════════════════════════════
#  ذخیره‌سازی و اجرا
# ══════════════════════════════════════════════════════════════
def get_license_file_path() -> Path:
    data_dir = app_paths.data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "license.dat"


def save_license(license_key: str, device_id: str, user_name: str = "") -> bool:
    try:
        license_data = {
            "license_key": license_key,
            "device_id": device_id,
            "user_name": user_name,
            "activated_at": datetime.now().isoformat(),
            "version": "2.0",
        }
        license_file = get_license_file_path()
        with open(license_file, "w", encoding="utf-8") as f:
            json.dump(license_data, f, indent=2, ensure_ascii=False)
        try:
            os.chmod(license_file, 0o600)   # فقط کاربر فعلی (در ویندوز no-op)
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"خطا در ذخیره لایسنس: {e}")
        return False


def load_license() -> dict | None:
    try:
        license_file = get_license_file_path()
        if not license_file.exists():
            return None
        with open(license_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def is_activated() -> bool:
    """کلید معتبرِ همین دستگاه + قفل device_id (جلوگیری از کپی license.dat)."""
    data = load_license()
    if not data:
        return False
    if data.get("device_id") != get_device_id():
        return False
    ok, _ = validate_license(data.get("license_key", ""))
    return ok


def activate_program(license_key: str, user_name: str = "") -> tuple[bool, str]:
    ok, message = validate_license(license_key)
    if not ok:
        return False, message
    if not save_license(license_key, get_device_id(), user_name):
        return False, "خطا در ذخیره لایسنس"
    return True, "برنامه با موفقیت فعال شد"


def deactivate_program() -> bool:
    try:
        f = get_license_file_path()
        if f.exists():
            f.unlink()
        return True
    except Exception as e:
        print(f"خطا در غیرفعال‌سازی: {e}")
        return False


def license_bypassed() -> bool:
    """حالت توسعه/تست: ODIN_SKIP_LICENSE=1 یا پلتفرم offscreen (CI/تست‌های GUI).

    کاربر نهایی هیچ‌وقت offscreen اجرا نمی‌کند؛ selftest پنل هم همین را ست می‌کند.
    """
    if os.environ.get("ODIN_SKIP_LICENSE") == "1":
        return True
    return os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"


def check_and_enforce_license() -> tuple[bool, str]:
    """دروازهٔ اجرا. Returns: (اجازهٔ ادامه, پیام)."""
    if license_bypassed():
        return True, "حالت توسعه/تست — لایسنس نادیده گرفته شد"
    if is_activated():
        return True, "لایسنس معتبر است"
    return False, "برنامه فعال نشده است. لطفاً با کلید لایسنس معتبر فعال‌سازی کنید."


# ══════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════
def _cli(argv: list[str]) -> int:
    cmd = (argv[0] if argv else "device").lower()
    if cmd == "device":
        did = get_device_id()
        print(f"شناسهٔ کامل دستگاه : {did}")
        print(f"کد دستگاه (برای سازنده): {get_device_code(did)}")
        return 0
    if cmd == "gen":
        if len(argv) < 2:
            print("کاربرد: python -m src.license gen <DEVICE-CODE>")
            return 2
        code = normalize_code(argv[1])
        try:
            print(generate_license_key(code))
        except ValueError as e:
            print(f"کد دستگاه نامعتبر: {e}")
            return 2
        return 0
    if cmd == "check":
        if len(argv) < 3:
            print("کاربرد: python -m src.license check <KEY> <DEVICE-CODE>")
            return 2
        ok, msg = validate_license(argv[1], argv[2])
        print(("✅ " if ok else "❌ ") + msg)
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
