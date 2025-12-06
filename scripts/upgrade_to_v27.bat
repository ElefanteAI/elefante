@echo off
echo ========================================
echo ELEFANTE v27.0 SEMANTIC TOPOLOGY UPGRADE
echo ========================================
echo.

echo Step 1: Running Topology Repair Script...
echo This will inject semantic relationships between memories
echo.
cd /d "%~dp0.."
python scripts/utils/repair_graph_topology.py
if errorlevel 1 (
    echo.
    echo ERROR: Topology repair failed!
    pause
    exit /b 1
)

echo.
echo Step 2: Updating Dashboard Data...
python scripts/update_dashboard_data.py
if errorlevel 1 (
    echo.
    echo ERROR: Dashboard data update failed!
    pause
    exit /b 1
)

echo.
echo Step 3: Restarting Dashboard...
echo Please manually restart the dashboard or run:
echo   cd src/dashboard/ui
echo   npm run dev
echo.
echo ========================================
echo v27.0 UPGRADE COMPLETE!
echo ========================================
echo.
echo NEXT STEPS:
echo 1. Hard refresh your browser (Ctrl+Shift+R)
echo 2. Look for purple header: "VERSION 27.0"
echo 3. Check debug overlay (top-right) for topology stats
echo.
echo EXPECTED RESULTS:
echo - Large RED/GOLD nodes (Identity Cluster)
echo - Large RED nodes (Critical Laws)
echo - Small BLUE nodes (Facts) orbiting larger concepts
echo - Debug box shows "HUBS (Imp 10): X"
echo.
pause

@REM Made with Bob
