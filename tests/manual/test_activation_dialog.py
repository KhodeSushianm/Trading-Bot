# -*- coding: utf-8 -*-
"""رگرسیون دیالوگ فعال‌سازی — کرش v0.19.0 روی ویندوز.

باگ: `_show_activation_dialog` از `T.primary` / `T.on_primary` استفاده می‌کرد
که در تم شیشه‌ای جدید (src/ui/theme.py) وجود ندارند →
    AttributeError: 'Theme' object has no attribute 'primary'
و چون دیالوگ فقط روی ماشینِ بدون لایسنس باز می‌شد، هیچ تستی آن را نمی‌دید.

دو لایه حفاظت:
  ۱) ایستا: هر ارجاع `T.x` / `DARK.x` / `LIGHT.x` در کد پایتون باید
     attribute واقعی کلاس Theme باشد (مچیده‌شده با ast از خود theme.py).
  ۲) زمان‌اجرا: ساخت واقعی دیالوگ فعال‌سازی به‌صورت offscreen، بدون exec بلاک‌کننده.

اجرا:  QT_QPA_PLATFORM=offscreen python tests/manual/test_activation_dialog.py
"""
import ast
import os
import pathlib
import re
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

FAILS = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAILS.append(msg)


# ───────────────────────── لایهٔ ۱: ممیزی ایستا ─────────────────────────
print("=" * 70)
print("۱) ممیزی ایستا: همهٔ توکن‌های تم باید در Theme وجود داشته باشند")
print("=" * 70)

_theme_src = (_ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
_attrs = set()
for node in ast.walk(ast.parse(_theme_src)):
    if isinstance(node, ast.ClassDef) and node.name == "Theme":
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                _attrs.add(item.target.id)
_attrs |= {"rgba"}  # متد کمکی

_py_files = ["panel.py", "main.py"]
_py_files += [str(p.relative_to(_ROOT)) for p in (_ROOT / "src").rglob("*.py")]
_bad = []
for rel in _py_files:
    code = (_ROOT / rel).read_text(encoding="utf-8")
    for m in re.finditer(r"\b(?:T|DARK|LIGHT)\.([A-Za-z_][A-Za-z0-9_]*)", code):
        attr = m.group(1)
        if attr not in _attrs:
            line = code[: m.start()].count("\n") + 1
            _bad.append(f"{rel}:{line} → .{attr}")
check(not _bad, "هیچ ارجاع تمِ نامعتبری وجود ندارد" + ("" if not _bad else ": " + "; ".join(_bad)))

# ───────────────────── لایهٔ ۲: ساخت واقعی دیالوگ ─────────────────────
print("=" * 70)
print("۲) ساخت دیالوگ فعال‌سازی (offscreen، exec پچ‌شده)")
print("=" * 70)

with tempfile.TemporaryDirectory() as td:
    os.environ["ODIN_DATA_DIR"] = td  # ایزوله‌سازی license.dat

    from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QPushButton

    app = QApplication.instance() or QApplication([])

    captured = {}

    def _fake_exec(self):  # جایگزین exec بلاک‌کننده
        captured["dlg"] = self
        return QDialog.DialogCode.Rejected

    QDialog.exec = _fake_exec

    import panel as panel_mod

    w = panel_mod.MainWindow.__new__(panel_mod.MainWindow)
    QMainWindow.__init__(w)  # فقط آبجکت C++ را می‌سازد؛ __init__ سنگین اجرا نمی‌شود

    err = None
    try:
        result = w._show_activation_dialog()
    except Exception as e:  # noqa: BLE001
        err = e
        result = None
    check(err is None, f"دیالوگ بدون خطا ساخته شد ({err!r})" if err else "دیالوگ بدون خطا ساخته شد")

    dlg = captured.get("dlg")
    check(dlg is not None, "QDialog ایجاد و به exec رسید")
    check(result is False, f"نتیجهٔ دیالوگ بدون فعال‌سازی False است (got {result!r})")

    # دکمهٔ «فعال‌سازی» باید رنگ جوهرِ تم را *resolve شده* داشته باشد،
    # نه placeholder خالی یا خطا
    from src.ui.theme import DARK

    btns = dlg.findChildren(QPushButton) if dlg is not None else []
    act = [b for b in btns if "فعال" in b.text()]
    check(len(act) == 1, "دکمهٔ «فعال‌سازی» پیدا شد")
    if act:
        ss = act[0].styleSheet()
        check(DARK.accent_ink.lower() in ss.lower(),
              "رنگ پس‌زمینهٔ دکمه = accent_ink تم (resolve شده)")
        check(DARK.on_ink.lower() in ss.lower(),
              "رنگ متن دکمه = on_ink تم (resolve شده)")

print("=" * 70)
if FAILS:
    print(f"❌ {len(FAILS)} خطا")
    sys.exit(1)
print("✅ همهٔ بررسی‌های دیالوگ فعال‌سازی پاس شد")
sys.exit(0)
