@echo off
title Razecheck Build
cd /d "%~dp0.."

echo.
echo  Razecheck - Build EXE
echo  Fill in client\config.json before continuing.
echo.
pause

echo.
echo [1/4] Installing client deps...
pip install -r client\requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 ( echo [ERROR] pip failed & pause & exit /b 1 )

echo [2/4] Installing PyInstaller...
pip install pyinstaller --quiet --disable-pip-version-check
if errorlevel 1 ( echo [ERROR] pyinstaller install failed & pause & exit /b 1 )

echo [3/4] Generating icon...
python client\assets\create_icon.py
if errorlevel 1 ( echo [ERROR] icon generation failed & pause & exit /b 1 )

echo [4/4] Building EXE...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name Razecheck ^
    --icon=client\assets\icon.ico ^
    --add-data "client\config.json;." ^
    --add-data "client\assets\icon.ico;assets" ^
    --paths client ^
    client\main.py

echo.
if exist "dist\Razecheck.exe" (
    echo [OK] Done! dist\Razecheck.exe
) else (
    echo [ERROR] Build failed - check output above.
)
echo.
pause
