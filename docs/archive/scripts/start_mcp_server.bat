@echo off
REM Elefante MCP Server Startup Script
REM This starts the MCP server for Claude Desktop integration

echo.
echo ============================================================
echo   ELEFANTE MCP SERVER
echo ============================================================
echo.
echo Starting Elefante MCP server...
echo Keep this window open while using Claude Desktop!
echo.
echo Press Ctrl+C to stop the server
echo ============================================================
echo.

cd /d "%~dp0"
cd ..

IF EXIST .venv (
    echo [INFO] Activating virtual environment...
    call .venv\Scripts\activate
) ELSE (
    echo [WARN] No .venv found. Trying global python...
)

python -m src.mcp.server

pause

