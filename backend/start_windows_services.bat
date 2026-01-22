@echo off
:: start_windows_services.bat
:: Starts Windows-based services for the Mumbai Geo-AI Backend

echo. ============================================================
echo.  STARTING WINDOWS SERVICES FOR MUMBAI GEO-AI BACKEND
echo. ============================================================

:: --- Start PostgreSQL Service ---
echo.
echo. [1/1] Attempting to start PostgreSQL service (postgresql-x64-16)...
echo.      (This might require Administrator privileges)
net start postgresql-x64-16
if %errorlevel% == 0 (
    echo.      [OK] PostgreSQL service started successfully.
) else (
    echo.      [INFO] PostgreSQL service might already be running or requires manual start via Services.msc
)

echo.
echo. ============================================================
echo.  WINDOWS SERVICES INITIATED
echo. ============================================================
echo.
echo. Next steps:
echo. 1. Start Redis in WSL (see separate instructions)
echo. 2. Double-click 'start_minio.bat'
echo. 3. Double-click 'start_titiler.bat'
echo.
pause