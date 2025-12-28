@echo off
REM One-Click Setup for VSCode/Bob Integration
REM Configures Elefante to auto-start with Bob AI Assistant

echo.
echo ============================================================
echo   🐘 ELEFANTE - VSCode/Bob Auto-Start Setup
echo ============================================================
echo.
echo This will configure Elefante to automatically start
echo every time you open VSCode/Bob.
echo.
echo Your AI assistant (Bob) will have persistent memory!
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause >nul

echo.
echo ============================================================
echo   Configuring VSCode/Bob...
echo ============================================================
echo.

cd /d "%~dp0"
python configure_vscode_bob.py

if errorlevel 1 (
    echo.
    echo ❌ Configuration failed!
    echo Please check VSCODE_BOB_SETUP.md for manual setup
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   ✅ SETUP COMPLETE!
echo ============================================================
echo.
echo 📋 NEXT STEPS:
echo.
echo   1. Close VSCode/Bob completely
echo   2. Reopen VSCode/Bob
echo   3. Elefante will auto-start with the AI assistant
echo   4. Test: Ask Bob "Remember that I'm Jaime from IBM Toronto"
echo   5. Query: Ask Bob "What do you know about me?"
echo.
echo 🎉 Bob now has persistent memory powered by Elefante!
echo.
echo ============================================================
echo.

pause

@REM Made with Bob
