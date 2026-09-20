# -*- coding: utf-8 -*-
"""تست رگرسیون منطق «پوشهٔ داده‌ها» (data_dir) — نسخهٔ ۰٫۸.

چرا: تا v0.7 همهٔ داده‌ها کنار EXE بودند. از v0.8 حالت «نصب‌شده» داده‌ها را به
%APPDATA%\\ODIN Assistant می‌برد (چون Program Files قابل‌نوشتن نیست) و حالت
«پرتابل» مثل قبل کنار EXE می‌ماند. اشتباه در این منطق یعنی توکن تلگرام یا
ژورنال گم‌شده — پس هر ۶ شاخه تست دارد. بدون اینترنت و بدون Qt (در CI اجرا می‌شود).

اجرا:  python tests/manual/test_paths_install.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src import app_paths  # noqa: E402


class _Frozen:
    """شبیه‌سازی حالت EXE: sys.frozen + sys.executable در یک پوشهٔ موقت."""

    def __init__(self, exe_dir: Path):
        self.exe_dir = exe_dir
        exe_dir.mkdir(parents=True, exist_ok=True)
        (exe_dir / "ODINAssistant.exe").write_bytes(b"MZ")

    def __enter__(self):
        self._frozen = getattr(sys, "frozen", None)
        self._exe = sys.executable
        self._appdata = os.environ.get("APPDATA")
        sys.frozen = True                                  # type: ignore[attr-defined]
        sys.executable = str(self.exe_dir / "ODINAssistant.exe")
        return self

    def __exit__(self, *exc):
        if self._frozen is None:
            del sys.frozen                                 # type: ignore[attr-defined]
        else:
            sys.frozen = self._frozen                      # type: ignore[attr-defined]
        sys.executable = self._exe
        if self._appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._appdata
        app_paths.clear_data_dir_cache()


def _reset():
    app_paths.clear_data_dir_cache()
    os.environ.pop(app_paths.DATA_DIR_ENV, None)


def test_dev_mode_uses_project_root():
    _reset()
    assert not app_paths.is_frozen()
    assert app_paths.data_dir() == app_paths.app_dir() == ROOT


def test_env_override_wins():
    _reset()
    with tempfile.TemporaryDirectory() as td:
        os.environ[app_paths.DATA_DIR_ENV] = td
        app_paths.clear_data_dir_cache()
        assert app_paths.data_dir() == Path(td).resolve()
    _reset()


def test_portable_marker_forces_exe_dir():
    _reset()
    with tempfile.TemporaryDirectory() as td:
        exe = Path(td) / "exe"
        app = Path(td) / "roaming"
        with _Frozen(exe) as f:
            os.environ["APPDATA"] = str(app)
            (f.exe_dir / app_paths.PORTABLE_MARKER).write_text("", encoding="utf-8")
            assert app_paths.data_dir() == f.exe_dir


def test_installed_marker_uses_appdata():
    _reset()
    with tempfile.TemporaryDirectory() as td:
        exe = Path(td) / "exe"
        app = Path(td) / "roaming"
        with _Frozen(exe) as f:
            os.environ["APPDATA"] = str(app)
            (f.exe_dir / app_paths.INSTALLED_MARKER).write_text("installed\n",
                                                                encoding="utf-8")
            d = app_paths.data_dir()
            assert d == app / app_paths.APP_NAME, d
            assert d.exists()


def test_legacy_portable_folder_keeps_exe_dir():
    """ارتقا از نسخهٔ ≤۰٫۷: پوشه‌ای که config.yaml/logs کنار EXE دارد پرتابل بماند."""
    _reset()
    with tempfile.TemporaryDirectory() as td:
        exe = Path(td) / "exe"
        app = Path(td) / "roaming"
        with _Frozen(exe) as f:
            os.environ["APPDATA"] = str(app)
            (f.exe_dir / "config.yaml").write_text("data_source: auto\n",
                                                   encoding="utf-8")
            assert app_paths.data_dir() == f.exe_dir


def test_fresh_portable_exe_uses_exe_dir():
    """EXE تازه در پوشهٔ کاربر (دسکتاپ/دانلودها) → داده کنار خودش (پرتابل)."""
    _reset()
    with tempfile.TemporaryDirectory() as td:
        exe = Path(td) / "exe"
        app = Path(td) / "roaming"
        with _Frozen(exe) as f:
            os.environ["APPDATA"] = str(app)
            assert app_paths.data_dir() == f.exe_dir


def test_protected_folder_falls_back_to_appdata():
    """کپی دستی در پوشهٔ محافظت‌شده (نوشتن ممنوع) → %APPDATA%."""
    _reset()
    real_writable = app_paths._is_writable
    app_paths._is_writable = lambda d: False          # noqa: E731
    try:
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / "exe"
            app = Path(td) / "roaming"
            with _Frozen(exe):
                os.environ["APPDATA"] = str(app)
                d = app_paths.data_dir()
                assert d == app / app_paths.APP_NAME, d
                assert d.exists()
    finally:
        app_paths._is_writable = real_writable
        _reset()


def test_config_and_journal_paths_follow_data_dir():
    _reset()
    with tempfile.TemporaryDirectory() as td:
        os.environ[app_paths.DATA_DIR_ENV] = td
        app_paths.clear_data_dir_cache()
        assert app_paths.config_path().parent == Path(td).resolve()
        assert app_paths.local_config_path().parent == Path(td).resolve()
        assert app_paths.logs_dir().parent == Path(td).resolve()
        assert app_paths.cache_dir().is_relative_to(Path(td).resolve())
    _reset()


def main() -> int:
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"SELFTEST OK — منطق پوشهٔ داده‌ها ({len(fns)} تست)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
