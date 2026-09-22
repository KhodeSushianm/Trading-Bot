# -*- coding: utf-8 -*-
"""استخراج «یادداشت ریلیز» برای یک نسخه از CHANGELOG.md.

استفاده:
    python installer/release_notes.py v0.20.1 > notes.md
    python installer/release_notes.py 0.20.1  --out notes.md
    python installer/release_notes.py            (از APP_VERSION در src/app_paths.py)

چرا لازم است؟
    متن Release پیش‌تر مستقیم داخل `build-release.yml` هاردکد شده بود و بعد از
    v0.8.1 به‌روز نشد؛ در نتیجه ۱۹ ریلیز پیاپی (v0.9.0 → v0.20.0) با یادداشتِ
    «تازه در v0.8.1» منتشر شدند. حالا یک منبع حقیقت داریم (CHANGELOG.md) و هر دو
    ورک‌فلو — ویندوز و اندروید — متن را از همین‌جا می‌خوانند، پس هرگز از هم
    واگرا نمی‌شوند.

قرارداد:
    هر بخش با «## [x.y.z] - YYYY-MM-DD» شروع می‌شود و تا نخستین «## [» بعدی
    ادامه دارد. بخش‌ها باید بین نشانگرهای RELEASE-NOTES-START/END باشند.

رفتار در حالت خطا (مهم):
    انتشار نسخه **هرگز** نباید به‌خاطر یک فایل مستندات بشکند. اگر بخش مربوطه
    پیدا نشود، یک یادداشت کوتاه ولی درست تولید می‌شود و کد خروج ۰ برمی‌گردد
    (فقط روی stderr هشدار می‌دهد). تنها در صورت نبودِ خودِ CHANGELOG.md
    کد خروج ۱ می‌شود، چون آن یعنی ریپو خراب است.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"

START = "<!-- RELEASE-NOTES-START -->"
END = "<!-- RELEASE-NOTES-END -->"

REPO = "KhodeSushianm/Trading-Bot"


def read_app_version() -> str:
    """APP_VERSION از src/app_paths.py — منبع حقیقت شمارهٔ نسخه."""
    txt = (ROOT / "src" / "app_paths.py").read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', txt)
    return m.group(1) if m else "0.0.0"


def normalize(v: str) -> str:
    """«v0.20.1» / «0.20.1» / «refs/tags/v0.20.1» → «0.20.1»"""
    v = v.strip().strip('"').strip("'")
    if v.startswith("refs/tags/"):
        v = v[len("refs/tags/"):]
    return v.lstrip("vV")


def extract_section(changelog: str, version: str) -> str | None:
    """بدنهٔ بخشِ یک نسخه را از CHANGELOG برمی‌گرداند (بدون خودِ سرتیتر)."""
    lo, hi = changelog.find(START), changelog.find(END)
    body = changelog[lo + len(START): hi] if lo != -1 and hi != -1 else changelog

    # سرتیترها را با موقعیتشان پیدا کن تا برش دقیق بزنیم
    heads = [(m.start(), m.group(1), m.group(0)) for m in re.finditer(r"^## \[([^\]]+)\]([^\n]*)", body, re.M)]
    for i, (pos, _ver, head_line) in enumerate(heads):
        # یک سرتیتر می‌تواند چند نسخه را پوشش دهد (مثل «## [0.7.2] · [0.7.1]»)
        versions = [normalize(x) for x in re.findall(r"\[([^\]]+)\]", head_line)]
        if version not in versions:
            continue
        end = heads[i + 1][0] if i + 1 < len(heads) else len(body)
        return body[pos:end].strip()
    return None


def fallback_body(version: str) -> str:
    """یادداشت کوتاه ولی درست وقتی بخشِ نسخه در CHANGELOG نیست."""
    return (
        f"## ODIN Assistant {version}\n\n"
        f"بخش این نسخه در `CHANGELOG.md` ثبت نشده است (این متن خودکار تولید شده).\n\n"
        f"برای دیدن فهرست کامل کامیت‌ها:\n"
        f"[مقایسه با نسخهٔ قبل](https://github.com/{REPO}/compare/v{version}%5E...v{version})\n"
    )


def build_body(version: str) -> tuple[str, bool]:
    """(متن یادداشت, آیا از CHANGELOG آمد؟)"""
    if not CHANGELOG.exists():
        raise FileNotFoundError(f"CHANGELOG.md پیدا نشد: {CHANGELOG}")
    changelog = CHANGELOG.read_text(encoding="utf-8")
    section = extract_section(changelog, version)
    if section is None:
        return fallback_body(version), False
    tail = (
        "\n---\n\n"
        "### 📦 فایل‌های این نسخه (Assets پایین همین صفحه)\n\n"
        "| فایل | پلتفرم |\n"
        "|---|---|\n"
        f"| `ODINAssistant-v{version}-windows-setup.exe` | ویندوز — نصب‌کنندهٔ رسمی (پیشنهادی) |\n"
        f"| `ODINAssistant-v{version}-windows.exe` | ویندوز — نسخهٔ پرتابل تک‌فایلی |\n"
        f"| `ODIN-Assistant-android-v{version}.apk` | اندروید — امضاشده با کلید رسمی |\n\n"
        "> ⚠️ ODIN هیچ معامله‌ای را خودکار اجرا نمی‌کند؛ تحلیل و پیشنهاد می‌دهد و\n"
        "> تصمیم نهایی با شماست. اگر هشدار آبی SmartScreen دیدید: **More info → Run anyway**.\n"
    )
    return section + tail, True


def main(argv: list[str] | None = None) -> int:
    # کنسول ویندوز cp1252 است؛ بدون این خط چاپ فارسی کرش می‌کند
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    p = argparse.ArgumentParser(description="ساخت یادداشت ریلیز از CHANGELOG.md")
    p.add_argument("version", nargs="?", default="", help="مثل v0.20.1 (پیش‌فرض: APP_VERSION)")
    p.add_argument("--out", default="", help="مسیر فایل خروجی (پیش‌فرض: stdout)")
    args = p.parse_args(argv)

    version = normalize(args.version) if args.version else read_app_version()
    try:
        body, from_changelog = build_body(version)
    except FileNotFoundError as e:
        print(f"[release_notes] ✗ {e}", file=sys.stderr)
        return 1

    if not from_changelog:
        print(
            f"[release_notes] ⚠ بخش [{version}] در CHANGELOG.md پیدا نشد — "
            f"یادداشت جایگزین تولید شد. انتشار متوقف نمی‌شود، ولی CHANGELOG را کامل کنید.",
            file=sys.stderr,
        )

    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"[release_notes] ✓ {args.out} ← v{version} ({len(body)} نویسه)", file=sys.stderr)
    else:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
