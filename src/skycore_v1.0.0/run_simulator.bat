@echo off
chcp 65001 >nul
title SkyCore Simulator
color 0B
cd /d "%~dp0"
py run.py --simulator
pause