# -*- coding: utf-8 -*-
"""تست رگرسیون چیدمان داشبورد (باگ‌های نسخهٔ ویندوز v0.7.1).

موارد بررسی در چند اندازهٔ پنجره (شامل اندازهٔ منطقی کاربر ۱۵۳۵×۸۶۳ و
حداقل ۱۰۲۰×۷۰۰):
  ۱. هیچ ویجت فرزندِ کارتی بیرون از مستطیل همان کارت نقاشی نشود
     (باگ سرریز حلقه/نمودار در پنجره‌های کوچک).
  ۲. برچسب‌های متنی داخل کارت مشکی رنگ روشن داشته باشند
     (باگ متن سیاه روی سیاه وقتی QSS القا نمی‌شود).
  ۳. اسکرول افقی داشبورد هرگز فعال نشود؛ عمودی در ارتفاع کم مجاز است.
  ۴. شمارش معکوس رویدادها خوانا باشد (نه دقیقهٔ خام بزرگ).

اجرا:  QT_QPA_PLATFORM=offscreen python3 tests/manual/test_layout_fit.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import QPoint, Qt, QTimer              # noqa: E402
from PySide6.QtGui import QPalette                         # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

import panel as P                                          # noqa: E402
from render_dash import build_state                        # noqa: E402
from src.fa import fa_countdown                            # noqa: E402
from src.ui.widgets import SoftCard                        # noqa: E402

SIZES = [(1535, 863), (1020, 700), (1920, 1080)]
TOL = 2          # تحمل پیکسلی برای لبه‌ها
FAILS: list[str] = []


def lum(col) -> float:
    return 0.2126 * col.redF() + 0.7152 * col.greenF() + 0.0722 * col.blueF()


def check_containment(w, tag: str) -> None:
    """هیچ فرزندی بیرون از مستطیل کارت میزبانش نباشد."""
    content = w.pages.widget(0).widget()
    for card in content.findChildren(SoftCard):
        for child in card.findChildren(QWidget):
            if child is card or not child.isVisibleTo(card):
                continue
            tl = child.mapTo(card, QPoint(0, 0))
            br = child.mapTo(card, QPoint(child.width() - 1, child.height() - 1))
            if (tl.x() < -TOL or tl.y() < -TOL
                    or br.x() > card.width() - 1 + TOL
                    or br.y() > card.height() - 1 + TOL):
                FAILS.append(f"{tag}: {child.objectName() or type(child).__name__} "
                             f"بیرون از کارت {type(card).__name__} "
                             f"({tl.x()},{tl.y()})-({br.x()},{br.y()}) "
                             f"کارت={card.width()}x{card.height()}")


def check_ink_text(w, tag: str) -> None:
    """متن روی کارت مشکی باید روشن باشد (سفید/خاکستری روشن/سبز-قرمز روشن)."""
    content = w.pages.widget(0).widget()
    for card in content.findChildren(SoftCard):
        if not card._ink:                                   # noqa: SLF001
            continue
        for lbl in card.findChildren(QLabel):
            if not lbl.text().strip():
                continue
            col = lbl.palette().color(QPalette.WindowText)
            if lum(col) < 0.45:
                FAILS.append(f"{tag}: برچسب تیره روی کارت مشکی: "
                             f"{lbl.objectName()!r} متن={lbl.text()!r} رنگ={col.name()}")


def check_scroll(w, tag: str) -> None:
    page = w.pages.widget(0)
    hb = page.horizontalScrollBar()
    if hb.maximum() > 0 or hb.isVisible():
        FAILS.append(f"{tag}: اسکرول افقی داشبورد فعال شده است")


def check_countdown() -> None:
    cases = {
        25: "۲۵ دقیقهٔ دیگر",
        59: "۵۹ دقیقهٔ دیگر",
        60: "۱ ساعت دیگر",
        185: "۳ ساعت و ۵ دقیقهٔ دیگر",
        1440: "۱ روز دیگر",
        1889: "۱ روز دیگر",
        2880: "۲ روز دیگر",
        -30: "۳۰ دقیقهٔ دیگر",
    }
    for minutes, want in cases.items():
        got = fa_countdown(minutes)
        if got != want:
            FAILS.append(f"fa_countdown({minutes}) = {got!r} انتظار {want!r}")


def main() -> int:
    P.app_paths.fix_console_encoding()
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)
    fam = P.load_fonts()
    from PySide6.QtGui import QFont
    app.setFont(QFont(fam, 11))
    app.setStyleSheet(P.build_qss(fam, check_img=P._check_img()))

    w = P.MainWindow(show_splash=False)
    w.loop.state.update(build_state())
    type(w.loop).running = property(lambda self: True)      # noqa: ARG005
    w._tick()
    w.show()

    def done():
        for (sw, sh) in SIZES:
            tag = f"{sw}x{sh}"
            w.resize(sw, sh)
            app.processEvents()
            w._tick()
            app.processEvents()
            check_containment(w, tag)
            check_ink_text(w, tag)
            check_scroll(w, tag)
        check_countdown()
        app.quit()

    QTimer.singleShot(900, done)
    app.exec()

    if FAILS:
        print(f"FAIL ({len(FAILS)}):")
        for f in FAILS:
            print("  -", f)
        return 1
    print("PASS: چیدمان داشبورد در همهٔ اندازه‌ها داخل کارت‌هاست، "
          "متن کارت مشکی روشن است، اسکرول افقی خاموش است و شمارش معکوس خواناست.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
