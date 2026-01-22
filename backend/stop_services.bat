@echo off

echo 🛑 Stopping Mumbai Geo-AI Backend Services...

REM Stop MinIO processes
echo Stopping MinIO...
taskkill /F /IM minio.exe >nul 2>&1
if %errorlevel%==0 (
    echo MinIO stopped
) else (
    echo MinIO was not running
)

REM Stop Titiler processes
echo Stopping Titiler...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001') do (
    taskkill /F /PID %%a >nul 2>&1
    if %errorlevel%==0 (
        echo Titiler stopped
    )
)

REM Stop Redis (if you want to stop the service)
echo Stopping Redis...
net stop Redis >nul 2>&1

REM Note: We don't stop PostgreSQL as it might be used by other applications

echo.
echo ✅ Services stopped!
echo Note: PostgreSQL service was left running (may be used by other applications)
echo.
pause