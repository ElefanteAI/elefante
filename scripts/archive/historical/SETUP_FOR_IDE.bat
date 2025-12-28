@echo off
REM Complete Elefante Setup for IDE Integration
REM This script configures everything you need to use Elefante with Claude Desktop

echo.
echo ============================================================
echo   ELEFANTE - Complete IDE Setup
echo ============================================================
echo.
echo This script will:
echo   1. Configure Claude Desktop to use Elefante
echo   2. Start the MCP server
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause >nul

echo.
echo ============================================================
echo   Step 1: Configuring Claude Desktop
echo ============================================================
echo.

python configure_claude_desktop.py

if errorlevel 1 (
    echo.
    echo [ERROR] Configuration failed!
    echo Manual setup docs: docs\technical\mcp-server-startup.md
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Step 2: Starting MCP Server
echo ============================================================
echo.
echo The MCP server will start now.
echo KEEP THIS WINDOW OPEN while using Claude Desktop!
echo.
echo Next steps:
echo   1. Restart Claude Desktop (close and reopen)
echo   2. Look for the 'Connected' indicator
echo   3. Test: "Remember that I'm Jaime from IBM Toronto"
echo.
echo Press any key to start the server...
pause >nul

echo.
echo Starting Elefante MCP Server...
echo Press Ctrl+C to stop
echo.

python -m src.mcp.server

pause

@REM Made with Bob
