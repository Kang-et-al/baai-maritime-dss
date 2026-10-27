@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python scripts\bootstrap.py
) else (
  py -3.12 scripts\bootstrap.py
)
if errorlevel 1 (
  echo Setup failed. Install Python 3.12 and see docs/SETUP.md.
  pause
  exit /b 1
)
echo Setup complete.
pause
