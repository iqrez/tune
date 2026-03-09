@echo off
echo Starting BaseTune Architect...

echo Starting Backend API...
start "BaseTune Backend" cmd /c "cd backend && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

timeout /t 2 /nobreak >nul

echo Starting Native UI...
start "BaseTune Native UI" cmd /c "py run_native_ui.py"

echo BaseTune Architect is launched! You can close this window.
