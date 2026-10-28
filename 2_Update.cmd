@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1" update
set "APP_EXIT=%ERRORLEVEL%"
pause
exit /b %APP_EXIT%
