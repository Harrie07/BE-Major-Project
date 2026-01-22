@echo off

echo 🚀 Starting Mumbai Geo-AI Backend Services...

REM Activate virtual environment
call venv\Scripts\activate

REM Start PostgreSQL (adjust service name if different)
echo Starting PostgreSQL...
net start postgresql-x64-15

REM Start Redis (if installed as service)
echo Starting Redis...
net start Redis

REM Check if MinIO exists
if not exist "minio.exe" (
    echo Downloading MinIO...
    powershell -Command "Invoke-WebRequest -Uri 'https://dl.min.io/server/minio/release/windows-amd64/minio.exe' -OutFile 'minio.exe'"
)

REM Create MinIO data directory
if not exist "minio-data" mkdir minio-data

REM Start MinIO in background
echo Starting MinIO...
start /B minio.exe server minio-data --console-address ":9001"
echo MinIO started

REM Wait a moment for MinIO to start
timeout /t 3 /nobreak >nul

REM Start Titiler in background
echo Starting Titiler...
start /B uvicorn titiler.core.main:app --host 0.0.0.0 --port 8001
echo Titiler started

echo.
echo ✅ All services started!
echo.
echo Services running on:
echo 📊 PostgreSQL: localhost:5432
echo 💾 Redis: localhost:6379
echo 🪣 MinIO: http://localhost:9000 (console: http://localhost:9001)
echo 🗺️  Titiler: http://localhost:8001
echo.
echo Run 'python test_setup.py' to verify all services are working.
echo Press any key to continue...
pause >nul