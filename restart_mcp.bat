@echo off
REM Restart MCP Server Script
REM This script helps restart the Elefante MCP server to clear stale database connections

echo ============================================================
echo RESTARTING ELEFANTE MCP SERVER
echo ============================================================
echo.

REM Find and kill any existing Python processes running the MCP server
echo [INFO] Checking for existing MCP server processes...
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr /I "PID"') do (
    echo Found Python process: %%a
    tasklist /FI "PID eq %%a" /V | findstr /I "mcp" >nul
    if not errorlevel 1 (
        echo [INFO] Stopping MCP server process %%a...
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
echo [INFO] MCP server processes cleared
echo [INFO] Bob IDE will automatically restart the MCP server when needed
echo.
echo ============================================================
echo RESTART COMPLETE
echo ============================================================
echo.
echo Next steps:
echo 1. The MCP server will auto-restart when you use MCP tools in Bob
echo 2. Try using addMemory or searchMemories tools
echo 3. If issues persist, restart Bob IDE completely
echo.
pause

