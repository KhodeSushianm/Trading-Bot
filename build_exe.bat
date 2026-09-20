@echo off
chcp 65001 >nul
title Build ODIN Assistant EXE
echo ============================================================
echo   Building ODINAssistant.exe (Windows)
echo   NOTE: The official installer + portable EXE are published on
echo         GitHub Releases (repo page ^> Releases) - you can just
echo         download and install them.
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python not found. Install from python.org and check "Add to PATH".
    pause
    exit /b 1
)

echo [1/4] Installing dependencies (may take a few minutes)...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [X] Dependency install failed.
    pause
    exit /b 1
)

echo.
echo [2/4] Stamping Windows version info...
python installer\stamp_version.py
if errorlevel 1 (
    echo [!] Version stamp skipped (non-fatal).
)

echo.
echo [3/4] Building EXE (3-8 minutes, one time)...
pyinstaller ODINAssistant.spec --noconfirm
if errorlevel 1 (
    echo [X] Build failed.
    pause
    exit /b 1
)

echo.
echo [4/4] Installer (optional - needs Inno Setup 6)...
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if defined ISCC (
    "%ISCC%" /DAppVersion=0.8.0 installer\odin.iss
    echo   Installer: installer\Output\ODINAssistant-v0.8.0-windows-setup.exe
) else (
    echo   [i] Inno Setup not found - portable EXE only. Get it from jrsoftware.org
    echo       or download the official installer from GitHub Releases.
)

echo.
echo Done!
echo.
echo   Portable EXE:  %CD%\dist\ODINAssistant.exe
echo   First launch takes 10-20 seconds (unpacking) - this is normal.
echo.
pause
