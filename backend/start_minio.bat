@echo off
:: start_minio.bat
:: Starts MinIO server for the Mumbai Geo-AI Backend

echo. ============================================================
echo.  STARTING MINIO SERVER FOR MUMBAI GEO-AI BACKEND
echo. ============================================================

:: Navigate to the project directory (adjust path if needed)
cd /d "C:\Users\Acer\mumbai-geo-ai-backend"

:: Check if minio.exe exists
if not exist "minio.exe" (
    echo.
    echo. [ERROR] minio.exe not found in the current directory.
    echo.         Make sure you are in the correct project folder.
    echo.         Current directory: %cd%
    echo.
    pause
    exit /b 1
)

echo.
echo. Starting MinIO server...
echo. Data directory: minio-data
echo. Console address: http://localhost:9001
echo. API address: http://localhost:9000
echo.
echo. MinIO will run in this window. Keep it open.
echo. To stop MinIO, close this window or press Ctrl+C.
echo.

:: Start MinIO
minio.exe server minio-data --console-address ":9001"

:: Pause to see any error messages if MinIO fails to start
pause