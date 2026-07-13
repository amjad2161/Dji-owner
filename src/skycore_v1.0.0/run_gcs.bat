@echo off
chcp 65001 >nul
title SkyCore GCS
color 0B
cd /d "%~dp0"
py run.py --gui --port 8080
pause