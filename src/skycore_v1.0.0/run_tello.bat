@echo off
chcp 65001 >nul
title SkyCore Tello
color 0B
cd /d "%~dp0"
py run.py --tello
pause