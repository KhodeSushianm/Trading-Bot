# -*- coding: utf-8 -*-
"""ساخت/به‌روزرسانی installer/version_info.txt (منبع VERSIONINFO ویندوز برای PyInstaller).

استفاده:
    python installer/stamp_version.py 0.8.0
    python installer/stamp_version.py v0.8.1        (پیشوند v حذف می‌شود)
    python installer/stamp_version.py               (از APP_VERSION در src/app_paths.py)

چرا لازم است؟ PyInstaller اطلاعات نسخهٔ فایل (Properties → Details) را فقط از یک
فایل VERSIONINFO می‌گیرد؛ بدون آن، EXE در ویندوز «بدون نسخه» دیده می‌شود و
نصب‌کننده/آنتی‌ویروس‌ها سخت‌تر اعتماد می‌کنند. CI این اسکریپت را قبل از ساخت EXE
با شمارهٔ تگ صدا می‌زند تا نسخهٔ داخل فایل با نسخهٔ Release یکی باشد.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "installer" / "version_info.txt"

_TEMPLATE = '''# -*- coding: utf-8 -*-
# تولید خودکار توسط installer/stamp_version.py — دستی ویرایش نکنید.
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=({tup}),
        prodvers=({tup}),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable(u'040904B0', [
                StringStruct(u'CompanyName', u'KhodeSushianm'),
                StringStruct(u'FileDescription', u'ODIN Assistant - forex analysis and signal assistant'),
                StringStruct(u'FileVersion', u'{ver}'),
                StringStruct(u'InternalName', u'ODINAssistant'),
                StringStruct(u'LegalCopyright', u'KhodeSushianm'),
                StringStruct(u'OriginalFilename', u'ODINAssistant.exe'),
                StringStruct(u'ProductName', u'ODIN Assistant'),
                StringStruct(u'ProductVersion', u'{ver}'),
            ]),
        ]),
        VarFileInfo([VarStruct(u'Translation', [1033, 1200])]),
    ],
)
'''


def read_app_version() -> str:
    txt = (ROOT / "src" / "app_paths.py").read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', txt)
    return m.group(1) if m else "0.0.0"


def main(argv: list[str]) -> int:
    v = (argv[1] if len(argv) > 1 else "").strip().lstrip("vV")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[.\-+][0-9A-Za-z.\-]+)?", v):
        v = read_app_version()
    core = re.split(r"[-+]", v)[0]
    nums = [int(x) for x in core.split(".")][:4]
    while len(nums) < 4:
        nums.append(0)
    tup = ", ".join(str(n) for n in nums)
    OUT.write_text(_TEMPLATE.format(ver=v, tup=tup), encoding="utf-8")
    print(f"[stamp_version] version_info.txt ← {v}  ({tup})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
