@echo off
rem Starts the shopping list app (Windows). Keep this window open while using it.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m kainos.server
) else (
    python -m kainos.server
)
pause
