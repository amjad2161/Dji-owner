@echo off
chcp 65001 >nul
title SkyCore - התקנה
color 0A

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║           SkyCore Drone Operating System v1.0.0          ║
echo  ║                    התקנה מהירה                           ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo [1/4] בודק התקנת Python...
py --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python לא מותקן!
    echo.
    echo הורד Python מ: https://www.python.org/downloads/
    echo וודא שמסמן ✅ "Add Python to PATH"
    pause
    exit /b 1
)
echo ✅ Python מותקן

echo.
echo [2/4] משדרג pip...
py -m pip install --upgrade pip --quiet

echo.
echo [3/4] מתקין תלויות...
py -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ❌ שגיאה בהתקנת תלויות
    echo.
    echo מתקין עם פרטים...
    py -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo ✅ תלויות מותקנות

echo.
echo [4/4] מתקין SkyCore...
py setup.py develop --quiet
if errorlevel 1 (
    echo ❌ שגיאה בהתקנת SkyCore
    pause
    exit /b 1
)
echo ✅ SkyCore מותקן

echo.
echo ═══════════════════════════════════════════════════════════
echo.
echo ✅ ההתקנה הושלמה בהצלחה!
echo.
echo להפעלה:
echo   run_simulator.bat    - הפעל סימולטור
echo   run_gcs.bat          - הפעל ממשק Web
echo   run_tello.bat        - הפעל עם DJI Tello
echo.
echo או השתמש בפקודה:
echo   py run.py --simulator
echo.
echo ═══════════════════════════════════════════════════════════
echo.
pause