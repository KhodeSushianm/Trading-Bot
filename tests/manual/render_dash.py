"""رندر آف‌اسکرین داشبورد برای بازبینی بصری (بدون شبکه).

init دقیقاً مثل main() پنل: Fusion + RTL + فونت + QSS.
کاربرد:
    QT_QPA_PLATFORM=offscreen python3 tests/manual/render_dash.py [out.png]
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import panel as P  # noqa: E402


def build_state() -> dict:
    now = time.time()
    return {
        "last_run": now - 180,
        "last_error": None,
        "last_vetoes": [],
        "calendar_ok": True,
        "news_count": 4,
        "last_signals": [],
        "signals_total": 0,
        "ranking": [("CHF", 0.56), ("EUR", 0.21), ("GBP", 0.05), ("AUD", -0.08),
                    ("NZD", -0.22), ("CAD", -0.41), ("USD", -0.55), ("JPY", -0.72)],
        "upcoming": [
            {"title_fa": "سخنرانی لاگارد (رئیس بانک مرکزی اروپا)",
             "country_fa": "منطقه یورو", "minutes": 1889, "impact": "MEDIUM"},
            {"title_fa": "BOC Gov Macklem Speaks",
             "country_fa": "کانادا", "minutes": 1794, "impact": "MEDIUM"},
            {"title_fa": "RBA Gov Bullock Speaks",
             "country_fa": "استرالیا", "minutes": 2515, "impact": "HIGH"},
        ],
    }


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "render_dash.png"
    size_w = int(sys.argv[2]) if len(sys.argv) > 2 else 1920
    size_h = int(sys.argv[3]) if len(sys.argv) > 3 else 1080
    P.app_paths.fix_console_encoding()
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)
    fam = P.load_fonts()
    app.setFont(QFont(fam, 11))
    app.setStyleSheet(P.build_qss(fam, check_img=P._check_img()))

    w = P.MainWindow(show_splash=False)
    w.resize(size_w, size_h)
    w.loop.state.update(build_state())
    type(w.loop).running = property(lambda self: True)   # noqa: ARG005
    w._tick()
    w.show()
    QTimer.singleShot(1200, app.quit)
    app.exec()
    w._tick()
    app.processEvents()
    img = w.grab()
    ok = img.save(out)
    print("saved", out, ok, img.width(), "x", img.height())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
