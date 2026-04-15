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

REM 1. Check for Python 3.11 - 3.13
echo [INFO] Checking for Python... >> "%LOG_FILE%"
set PYTHON_CMD=

REM Try strictly supported python versions
for %%P in (python3.13 python3.12 python3.11 python3 python) do (
    %%P -c "import sys; sys.exit(0 if (3,11) <= sys.version_info < (3,14) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD=%%P
        goto :python_found
    )
)

:python_found
if not defined PYTHON_CMD (
    echo [ERROR] No compatible Python found. Requires 3.11, 3.12, or 3.13.
    echo [ERROR] No compatible Python found. Requires 3.11, 3.12, or 3.13. >> "%LOG_FILE%"
    echo Python 3.14+ is NOT supported due to Pydantic V1 limits.
    echo Please install Python 3.13 from https://python.org
    pause
    exit /b 1
)

%PYTHON_CMD% --version >> "%LOG_FILE%" 2>&1

echo [INFO] Repository virtual environment strategy will be handled by install.py >> "%LOG_FILE%"

REM 2. Run Python Installer
echo [INFO] Starting installation wizard...
echo [INFO] Starting installation wizard... >> "%LOG_FILE%"
%PYTHON_CMD% scripts\setup\install.py --log-file "%LOG_FILE%"

REM Keep window open if run from explorer
echo.
pause
