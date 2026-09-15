@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title MTV MAP Companion

echo MTV MAP Companion
echo =================

call :find_python
if defined PYTHON goto :run

echo.
echo Python 3.10 or newer was not found.
where winget >nul 2>nul
if %errorlevel%==0 (
  echo Installing Python 3.12 for the current user with Windows Package Manager...
  winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :python_web
  call :find_python
  if defined PYTHON goto :run
  if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PYTHON=%LocalAppData%\Programs\Python\Python312\python.exe"
    goto :run
  )
)

:python_web
echo.
echo Automatic Python installation was unavailable or did not complete.
echo Opening the official Python download page...
start "" "https://www.python.org/downloads/windows/"
echo Install Python 3.10 or newer, then double-click this file again.
pause
exit /b 1

:run
if defined PYTHON_ARGS (
  %PYTHON% %PYTHON_ARGS% bootstrap.py
) else (
  "%PYTHON%" bootstrap.py
)
set "STATUS=%ERRORLEVEL%"
if not "%STATUS%"=="0" pause
exit /b %STATUS%

:find_python
set "PYTHON="
set "PYTHON_ARGS="
for %%P in (py.exe python3.14.exe python3.13.exe python3.12.exe python3.11.exe python3.10.exe python.exe) do (
  where %%P >nul 2>nul
  if not errorlevel 1 (
    if /I "%%P"=="py.exe" (
      py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
      if not errorlevel 1 (
        set "PYTHON=py"
        set "PYTHON_ARGS=-3"
      )
    ) else (
      %%P -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
      if not errorlevel 1 set "PYTHON=%%P"
    )
    if defined PYTHON exit /b 0
  )
)
exit /b 1
