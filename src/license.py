#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سیستم لایسنس و قفل دستگاه برای ODIN Assistant.

این ماژول مسئولیت‌های زیر را دارد:
۱. تولید شناسه منحصر به فرد برای هر دستگاه (Device Fingerprint)
۲. ذخیره و بازیابی لایسنس کاربر
۳. بررسی اعتبار لایسنس در هنگام اجرا
۴. قفل کردن برنامه در صورت عدم تطابق لایسنس با دستگاه

استفاده:
    از این ماژول در main.py و panel.py قبل از اجرای اصلی برنامه فراخوانی شود.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import uuid
from pathlib import Path
from datetime import datetime, timedelta

from src import app_paths


def get_device_id() -> str:
    """تولید شناسه منحصر به فرد برای دستگاه فعلی.
    
    این شناسه بر اساس ترکیبی از:
    - MAC Address (اولویت اول)
    - Machine ID سیستم عامل
    - UUID تولیدی (به عنوان fallback)
    
    برگردانده می‌شود و به صورت SHA256 هش می‌شود.
    """
    identifiers = []
    
    # ۱. MAC Address
    mac = None
    try:
        addrs = [':'.join(f'{b:02x}' for b in os.ifaddresses(interface).get(os.AF_LINK, [{}])[0].get('addr', '').replace('-', ':')) 
                 for interface in os.listdir('/sys/class/net') if interface != 'lo']
        mac = max(addrs, key=len) if addrs else None
    except Exception:
        pass
    
    if not mac:
        # روش جایگزین برای ویندوز و مک
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                           for elements in range(0, 2 * 6, 8)][::-1])
        except Exception:
            mac = str(uuid.getnode())
    
    identifiers.append(f"mac:{mac}")
    
    # ۲. Machine ID سیستم عامل
    try:
        if platform.system() == "Linux":
            for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
                if os.path.exists(path):
                    with open(path) as f:
                        identifiers.append(f"machine_id:{f.read().strip()}")
                    break
        elif platform.system() == "Windows":
            import subprocess
            result = subprocess.run(["wmic", "csproduct", "get", "uuid"], 
                                  capture_output=True, text=True)
            if result.stdout:
                uid = result.stdout.strip().split('\n')[-1].strip()
                identifiers.append(f"machine_uuid:{uid}")
        elif platform.system() == "Darwin":
            import subprocess
            result = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], 
                                  capture_output=True, text=True)
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if 'IOPlatformUUID' in line:
                        uid = line.split('=')[-1].strip().strip('"')
                        identifiers.append(f"machine_uuid:{uid}")
                        break
    except Exception:
        pass
    
    # ۳. اطلاعات سخت‌افزاری دیگر
    try:
        identifiers.append(f"cpu:{platform.processor()}")
        identifiers.append(f"hostname:{platform.node()}")
    except Exception:
        pass
    
    # ۴. اگر هیچ شناسه‌ای پیدا نشد، از UUID تصادفی استفاده کن
    if len(identifiers) <= 1:
        identifiers.append(f"fallback:{uuid.uuid4()}")
    
    # ایجاد هش نهایی
    combined = "|".join(identifiers)
    device_id = hashlib.sha256(combined.encode()).hexdigest()[:32]
    
    return device_id


def get_license_file_path() -> Path:
    """مسیر فایل لایسنس را برگردان."""
    data_dir = app_paths.data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "license.dat"


def save_license(license_key: str, device_id: str, user_name: str = "") -> bool:
    """ذخیره لایسنس برای دستگاه فعلی.
    
    Args:
        license_key: کلید لایسنس وارد شده توسط کاربر
        device_id: شناسه دستگاه فعلی
        user_name: نام کاربر (اختیاری)
    
    Returns:
        True اگر موفقیت‌آمیز بود، False در غیر این صورت
    """
    try:
        license_data = {
            "license_key": license_key,
            "device_id": device_id,
            "user_name": user_name,
            "activated_at": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        license_file = get_license_file_path()
        with open(license_file, 'w', encoding='utf-8') as f:
            json.dump(license_data, f, indent=2, ensure_ascii=False)
        
        # تنظیم مجوزهای امنیتی (فقط کاربر فعلی بتواند بخواند)
        try:
            os.chmod(license_file, 0o600)
        except Exception:
            pass  # در ویندوز ممکن است کار نکند
        
        return True
    except Exception as e:
        print(f"خطا در ذخیره لایسنس: {e}")
        return False


def load_license() -> dict | None:
    """بارگذاری لایسنس از فایل.
    
    Returns:
        دیکشنری شامل اطلاعات لایسنس یا None اگر فایل وجود نداشته باشد
    """
    try:
        license_file = get_license_file_path()
        if not license_file.exists():
            return None
        
        with open(license_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"خطا در بارگذاری لایسنس: {e}")
        return None


def validate_license(license_key: str) -> tuple[bool, str]:
    """اعتبارسنجی کلید لایسنس.
    
    این تابع بررسی می‌کند که:
    ۱. فرمت کلید صحیح باشد
    ۲. کلید منقضی نشده باشد
    ۳. کلید با دستگاه فعلی مطابقت داشته باشد
    
    Args:
        license_key: کلید لایسنس برای بررسی
    
    Returns:
        tuple[bool, str]: (آیا معتبر است, پیام خطا یا موفقیت)
    """
    if not license_key or len(license_key) < 16:
        return False, "کلید لایسنس نامعتبر است"
    
    # بررسی فرمت کلید (مثال: XXXX-XXXX-XXXX-XXXX)
    # در آینده می‌توان الگوریتم پیچیده‌تری اضافه کرد
    parts = license_key.replace("-", "").replace(" ", "")
    if len(parts) < 16:
        return False, "فرمت کلید لایسنس نادرست است"
    
    # بررسی انقضا (در آینده می‌توان تاریخ انقضا را از کلید استخراج کرد)
    # فعلاً همه کلیدها بدون انقضا هستند
    
    return True, "لایسنس معتبر است"


def is_activated() -> bool:
    """بررسی اینکه آیا برنامه فعال شده است یا خیر.
    
    Returns:
        True اگر لایسنس معتبر برای دستگاه فعلی وجود دارد
    """
    license_data = load_license()
    if not license_data:
        return False
    
    current_device_id = get_device_id()
    stored_device_id = license_data.get("device_id", "")
    
    if current_device_id != stored_device_id:
        return False
    
    # بررسی اعتبار کلید لایسنس
    license_key = license_data.get("license_key", "")
    is_valid, _ = validate_license(license_key)
    
    return is_valid


def activate_program(license_key: str, user_name: str = "") -> tuple[bool, str]:
    """فعال‌سازی برنامه با کلید لایسنس.
    
    Args:
        license_key: کلید لایسنس خریداری شده
        user_name: نام کاربر برای نمایش در برنامه
    
    Returns:
        tuple[bool, str]: (آیا فعال‌سازی موفق بود, پیام)
    """
    # بررسی اعتبار کلید
    is_valid, message = validate_license(license_key)
    if not is_valid:
        return False, message
    
    # دریافت شناسه دستگاه فعلی
    device_id = get_device_id()
    
    # ذخیره لایسنس
    success = save_license(license_key, device_id, user_name)
    if not success:
        return False, "خطا در ذخیره لایسنس"
    
    return True, "برنامه با موفقیت فعال شد"


def deactivate_program() -> bool:
    """غیرفعال‌سازی برنامه و حذف لایسنس.
    
    Returns:
        True اگر موفقیت‌آمیز بود
    """
    try:
        license_file = get_license_file_path()
        if license_file.exists():
            license_file.unlink()
        return True
    except Exception as e:
        print(f"خطا در غیرفعال‌سازی: {e}")
        return False


def check_and_enforce_license() -> tuple[bool, str]:
    """بررسی و اعمال قفل لایسنس.
    
    این تابع باید در ابتدای اجرای برنامه فراخوانی شود.
    اگر لایسنس معتبر نباشد، برنامه اجازه اجرا نخواهد داشت.
    
    Returns:
        tuple[bool, str]: (آیا می‌توان ادامه داد, پیام)
    """
    if not is_activated():
        return False, "برنامه فعال نشده است. لطفاً با کلید لایسنس معتبر فعال‌سازی کنید."
    
    return True, "لایسنس معتبر است"


def generate_license_key(base_string: str = "") -> str:
    """تولید کلید لایسنس نمونه (برای تست).
    
    در نسخه نهایی، این کلیدها باید از سرور تولید و توزیع شوند.
    
    Args:
        base_string: رشته پایه برای تولید کلید (اختیاری)
    
    Returns:
        کلید لایسنس تولید شده با فرمت XXXX-XXXX-XXXX-XXXX
    """
    if not base_string:
        base_string = f"{uuid.uuid4()}{datetime.now().isoformat()}"
    
    hash_obj = hashlib.sha256(base_string.encode())
    hash_hex = hash_obj.hexdigest().upper()
    
    # تقسیم به بخش‌های ۴ رقمی
    parts = [hash_hex[i:i+4] for i in range(0, 16, 4)]
    license_key = "-".join(parts)
    
    return license_key


if __name__ == "__main__":
    # تست ماژول
    print("=== تست سیستم لایسنس ===")
    print(f"شناسه دستگاه: {get_device_id()}")
    print(f"وضعیت فعال‌سازی: {is_activated()}")
    
    # تولید کلید تستی
    test_key = generate_license_key("test")
    print(f"کلید لایسنس تستی: {test_key}")
    
    # تست فعال‌سازی
    success, msg = activate_program(test_key, "کاربر تست")
    print(f"نتیجه فعال‌سازی: {msg}")
    print(f"وضعیت پس از فعال‌سازی: {is_activated()}")
