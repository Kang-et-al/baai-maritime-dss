@echo off
cd /d "%~dp0"
set "run_dir=outputs\demo_%RANDOM%_%RANDOM%"
call run_simulation.bat run --config configs\baseline.json --experiment replay --output "%run_dir%"
if errorlevel 1 exit /b 1
start "" "%CD%\%run_dir%\dashboard.html"
