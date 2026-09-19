@echo off
chcp 65001 >nul
title Build ForexAssistant EXE
echo ============================================================
echo   Building ForexAssistant.exe (Windows)
echo   NOTE: The official EXE is also published on GitHub Releases
echo         (repo page ^> Releases) - you can just download it.
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python not found. Install from python.org and check "Add to PATH".
    pause
    exit /b 1
)

echo [1/3] Installing dependencies (may take a few minutes)...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [X] Dependency install failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building EXE (3-8 minutes, one time)...
pyinstaller ForexAssistant.spec --noconfirm
if errorlevel 1 (
    echo [X] Build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo.
echo   EXE file:  %CD%\dist\ForexAssistant.exe
echo   First launch takes 10-20 seconds (unpacking) - this is normal.
echo.
pause
