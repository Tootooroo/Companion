@echo off
setlocal
cd /d "%~dp0"
title MTV MAP Companion
echo MTV MAP Companion
echo =================
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 bootstrap.py
  goto :end
)
where python >nul 2>nul
if %errorlevel%==0 (
  python bootstrap.py
  goto :end
)
echo.
echo Python 3.10 or newer is required.
echo Install Python from python.org and enable "Add Python to PATH".
echo Then double-click START_COMPANION.bat again.
echo.
pause
exit /b 1
:end
if errorlevel 1 pause
