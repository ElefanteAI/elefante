@echo off
REM Elefante Automated Deployment Script for Windows
REM This script automates the deployment process as much as possible

setlocal enabledelayedexpansion

echo ============================================================
echo ELEFANTE AUTOMATED DEPLOYMENT
echo ============================================================
echo.

REM Check if Python is installed
echo Checking prerequisites...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed. Please install Python 3.9 or higher.
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python found: %PYTHON_VERSION%
echo.

REM Step 1: Install dependencies
echo ============================================================
echo STEP 1: Installing Dependencies
echo ============================================================
echo [INFO] This may take 5-10 minutes on first run...
echo.

python -m pip install --upgrade pip >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip
    exit /b 1
)
echo [OK] pip upgraded

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    echo [INFO] Try manually: pip install -r requirements.txt
    exit /b 1
)
echo [OK] All dependencies installed successfully
echo.

REM Step 2: Initialize databases
echo ============================================================
echo STEP 2: Initializing Databases
echo ============================================================
echo.

python scripts\init_databases.py
if errorlevel 1 (
    echo [ERROR] Database initialization failed
    exit /b 1
)
echo [OK] Databases initialized successfully
echo.

REM Step 3: Run health check
echo ============================================================
echo STEP 3: Running Health Check
echo ============================================================
echo.

python scripts\health_check.py
if errorlevel 1 (
    echo [ERROR] Health check failed
    exit /b 1
)
echo [OK] Health check passed
echo.

REM Step 4: Run end-to-end tests
echo ============================================================
echo STEP 4: Running End-to-End Tests
echo ============================================================
echo.

python scripts\test_end_to_end.py
if errorlevel 1 (
    echo [ERROR] Tests failed
    exit /b 1
)
echo [OK] All tests passed!
echo.

REM Step 5: GitHub setup (interactive)
echo ============================================================
echo STEP 5: GitHub Setup (Optional)
echo ============================================================
echo.

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo [WARNING] No Git remote configured
    echo.
    echo [INFO] To push to GitHub:
    echo   1. Create a repository at https://github.com/new
    echo   2. Run: git remote add origin https://github.com/YOUR_USERNAME/elefante.git
    echo   3. Run: git push -u origin main
) else (
    for /f "delims=" %%i in ('git remote get-url origin') do set REMOTE_URL=%%i
    echo [OK] Git remote already configured
    echo [INFO] Remote URL: !REMOTE_URL!
    echo.
    
    set /p PUSH_NOW="Push to GitHub now? (y/n): "
    if /i "!PUSH_NOW!"=="y" (
        git push -u origin main
        if errorlevel 1 (
            echo [WARNING] Push failed. You may need to authenticate or create the repo first.
        ) else (
            echo [OK] Code pushed to GitHub successfully
        )
    ) else (
        echo [INFO] Skipping GitHub push. You can push later with: git push -u origin main
    )
)
echo.

REM Final summary
echo ============================================================
echo DEPLOYMENT COMPLETE!
echo ============================================================
echo.
echo [OK] Elefante is ready to use!
echo.
echo Next steps:
echo   1. Start MCP server: python -m src.mcp.server
echo   2. Configure your IDE (see DEPLOYMENT_GUIDE.md)
echo   3. Start using persistent AI memory!
echo.
echo Documentation:
echo   - README.md - Quick start guide
echo   - ARCHITECTURE.md - System design
echo   - DEPLOYMENT_GUIDE.md - Detailed deployment steps
echo.
echo [OK] Happy memory building!
echo.

pause

