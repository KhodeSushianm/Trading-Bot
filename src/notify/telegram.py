# -*- coding: utf-8 -*-
"""ارسال پیام به تلگرام از طریق Bot API (کاملاً رایگان، بدون کتابخانه اضافه).

- گزارش‌های بلند به‌صورت خودکار به بخش‌های زیر ۳۹۰۰ کاراکتر تقسیم می‌شوند
  (محدودیت تلگرام ۴۰۹۶ است).
- خطای 429 (محدودیت نرخ) یک بار با صبر کردن جبران می‌شود.
"""
from __future__ import annotations

import time

import requests

_API = "https://api.telegram.org/bot{token}/{method}"
_MAX_LEN = 3900


def _chunks(text: str, size: int = _MAX_LEN) -> list[str]:
    """تقسیم متن به قطعات حداکثر size کاراکتری، با مرز خطوط."""
    if len(text) <= size:
        return [text]
    out: list[str] = []
    cur = ""
    for line in text.splitlines(keepends=True):
        if len(cur) + len(line) > size:
            if cur:
                out.append(cur)
            while len(line) > size:      # خط خیلی بلند
                out.append(line[:size])
                line = line[size:]
            cur = line
        else:
            cur += line
    if cur:
        out.append(cur)
    return out


def validate_token(token: str) -> tuple[bool, str]:
    """اعتبار توکن بات را بررسی می‌کند. خروجی: (موفقیت، نام‌کاربری یا پیام خطا)."""
    try:
        r = requests.get(_API.format(token=token, method="getMe"), timeout=12)
        d = r.json()
        if d.get("ok"):
            return True, "@" + d["result"].get("username", "?")
        return False, str(d.get("description", "توکن نامعتبر است"))
    except Exception as e:
        return False, f"خطای اتصال: {str(e)[:70]}"


def get_chat_id(token: str) -> tuple[str | None, str]:
    """شناسه چت کاربر را از آخرین پیام‌های دریافتی بات می‌خواند.

    پیش‌نیاز: کاربر قبلاً به بات پیام داده باشد (مثلاً /start).
    """
    try:
        r = requests.get(_API.format(token=token, method="getUpdates"), timeout=12)
        d = r.json()
        if not d.get("ok"):
            return None, str(d.get("description", "خطای نامشخص"))
        for u in reversed(d.get("result") or []):
            msg = u.get("message") or u.get("channel_post") or u.get("edited_message")
            chat = (msg or {}).get("chat") or {}
            if chat.get("id") is not None:
                who = chat.get("first_name") or chat.get("title") or ""
                uname = f" (@{chat['username']})" if chat.get("username") else ""
                return str(chat["id"]), f"چت پیدا شد: {who}{uname}"
        return None, ("پیامی یافت نشد — اول در تلگرام بات خودت را باز کن و یک بار "
                      "/start بفرست، سپس دوباره این دکمه را بزن")
    except Exception as e:
        return None, f"خطای اتصال: {str(e)[:70]}"


def send_message(token: str, chat_id: str, text: str, timeout: int = 15) -> tuple[bool, str]:
    """ارسال متن (با تقسیم خودکار). خروجی: (موفقیت، پیام توصیفی فارسی)."""
    if not token or not chat_id:
        return False, "توکن یا شناسه چت تنظیم نشده است"
    url = _API.format(token=token, method="sendMessage")
    payload_base = {"chat_id": chat_id, "disable_web_page_preview": True}
    sent = 0
    for part in _chunks(text):
        payload = {**payload_base, "text": part}
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            if r.status_code == 429:
                wait = int(r.json().get("parameters", {}).get("retry_after", 3)) + 1
                time.sleep(min(wait, 30))
                r = requests.post(url, json=payload, timeout=timeout)
            d = r.json()
            if not d.get("ok"):
                return False, f"تلگرام خطا داد: {d.get('description', f'HTTP {r.status_code}')}"
            sent += 1
        except Exception as e:
            return False, f"خطای اتصال به تلگرام: {str(e)[:80]}"
    return True, f"{sent} پیام ارسال شد ✅"
