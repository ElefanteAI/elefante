@echo off
REM Elefante One-Click Installer for Windows
REM ========================================

setlocal enabledelayedexpansion

set LOG_FILE=%~dp0install.log

echo ============================================================ > "%LOG_FILE%"
echo  ELEFANTE INSTALLATION LOG >> "%LOG_FILE%"
echo Started at: %DATE% %TIME% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

echo ============================================================
echo  ELEFANTE INSTALLER
echo ============================================================
echo.

REM 1. Check for Python 3.11 explicitly (mandatory)
echo [INFO] Checking for Python 3.11... >> "%LOG_FILE%"
set PYTHON_CMD=
python3.11 --version >nul 2>&1 && set PYTHON_CMD=python3.11
if not defined PYTHON_CMD (
    python --version >nul 2>&1 && set PYTHON_CMD=python
)
if not defined PYTHON_CMD (
    echo [ERROR] Python is not installed or not in PATH.
    echo [ERROR] Python is not installed or not in PATH. >> "%LOG_FILE%"
    echo Please install Python 3.11 from https://python.org
    pause
    exit /b 1
)

for /f "tokens=1,2 delims=. " %%a in ('%PYTHON_CMD% --version 2^>^&1') do (
    set MAJOR=%%b
    set MINOR=%%c
    goto :version_checked
)
:version_checked
if not "%MAJOR%.%MINOR%"=="3.11" (
    echo [ERROR] Python 3.11 is required but found %MAJOR%.%MINOR%.
    echo [ERROR] Python 3.11 is required but found %MAJOR%.%MINOR%. >> "%LOG_FILE%"
    echo Install Python 3.11 and re-run: python3.11 -m venv .venv
    pause
    exit /b 1
)

%PYTHON_CMD% --version >> "%LOG_FILE%" 2>&1

REM 2. Create Virtual Environment
if not exist .venv (
    echo [INFO] Creating virtual environment...
    echo [INFO] Creating virtual environment... >> "%LOG_FILE%"
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        echo [ERROR] Failed to create virtual environment. >> "%LOG_FILE%"
        pause
        exit /b 1
    )
) else (
    echo [INFO] Virtual environment already exists. >> "%LOG_FILE%"
)

REM 3. Activate Virtual Environment
echo [INFO] Activating virtual environment... >> "%LOG_FILE%"
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    echo [ERROR] Failed to activate virtual environment. >> "%LOG_FILE%"
    pause
    exit /b 1
)

REM 4. Run Python Installer
echo [INFO] Starting installation wizard...
echo [INFO] Starting installation wizard... >> "%LOG_FILE%"
python scripts\install.py --log-file "%LOG_FILE%"

REM Keep window open if run from explorer
echo.
pause
