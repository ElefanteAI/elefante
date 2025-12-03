@echo off
echo Restarting Elefante Dashboard...
echo.

REM Kill any existing dashboard servers
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo Stopping process %%a on port 8000...
    taskkill /F /PID %%a 2>nul
)

timeout /t 2 /nobreak >nul

echo Starting dashboard server...
cd /d "%~dp0"
start "Elefante Dashboard" .venv\Scripts\python.exe -m src.dashboard.server

echo.
echo Dashboard starting at http://127.0.0.1:8000
echo Press Ctrl+C in the dashboard window to stop it.
echo.
pause

@REM Made with Bob
