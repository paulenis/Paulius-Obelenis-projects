@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Pirmas paleidimas: diegiama, luktelkite...
  python -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt
)
set
BUDGET_HOST=0.0.0.0
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:5000"
.venv\Scripts\python app.py
pause
