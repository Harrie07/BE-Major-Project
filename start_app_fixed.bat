@echo off
echo ================================================
echo Starting Mumbai Geo AI Backend...
echo ================================================

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate
if errorlevel 1 (
    echo ❌ Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install missing dependencies if needed
echo Checking dependencies...
pip install pydantic-settings --quiet

REM Set PROJ library path with multiple fallback locations
echo Setting up geospatial environment...
set PROJ_LIB=%CD%\venv\Lib\site-packages\pyproj\proj_dir\share\proj

REM Try alternative PROJ locations if first doesn't exist
if not exist "%PROJ_LIB%\proj.db" (
    echo First PROJ location not found, trying alternatives...
    set PROJ_LIB=%CD%\venv\Lib\site-packages\proj\share\proj
    if not exist "%PROJ_LIB%\proj.db" (
        set PROJ_LIB=%CD%\venv\share\proj
    )
)

echo 🗺️  PROJ_LIB set to: %PROJ_LIB%

REM Verify the PROJ database exists
if exist "%PROJ_LIB%\proj.db" (
    echo ✅ Found PROJ database at: %PROJ_LIB%\proj.db
) else (
    echo ⚠️  PROJ database not found. Continuing anyway...
    echo The application might work without explicit PROJ_LIB setting.
)

REM Set additional geospatial environment variables
set GDAL_DATA=%CD%\venv\Lib\site-packages\rasterio\gdal_data
set GDAL_DRIVER_PATH=%CD%\venv\Lib\site-packages\rasterio\gdal_plugins

echo.
echo 🌍 Starting Mumbai Geo-AI FastAPI application...
echo 📍 Your Swagger UI will be available at: http://localhost:8000/docs
echo 🔗 Health check at: http://localhost:8000/health
echo 🔗 API endpoints at: http://localhost:8000/api/v1/
echo.

REM Start YOUR FastAPI application (NOT TiTiler)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

echo.
echo Application stopped.
pause