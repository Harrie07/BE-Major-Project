@echo off
:: start_titiler.bat
:: Starts TiTiler service for the Mumbai Geo-AI Backend

echo ============================================================
echo  STARTING TITILER SERVICE FOR MUMBAI GEO-AI BACKEND
echo ============================================================

:: Navigate to the project directory (adjust path if needed)
cd /d "C:\Users\Acer\mumbai-geo-ai-backend"

:: Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo.
    echo [ERROR] Python virtual environment (venv) not found.
    echo         Make sure 'venv' folder exists in the project directory.
    echo         Current directory: %cd%
    echo.
    pause
    exit /b 1
)

:: Activate virtual environment
echo.
echo Activating Python virtual environment...
call venv\Scripts\activate.bat
if not defined VIRTUAL_ENV (
    echo.
    echo [ERROR] Failed to activate virtual environment.
    echo.
    pause
    exit /b 1
)
echo [OK] Virtual environment activated.

:: Set PROJ_LIB environment variable to avoid conflicts
:: Adjust the path if your rasterio/proj_data is located elsewhere within venv
set PROJ_LIB=%cd%\venv\Lib\site-packages\rasterio\proj_data
echo.
echo Setting PROJ_LIB environment variable: %PROJ_LIB%
if not exist "%PROJ_LIB%\proj.db" (
    echo [WARNING] proj.db not found at %PROJ_LIB%. TiTiler might encounter PROJ errors.
    echo           You might need to locate the correct proj_data folder within your venv.
)

echo.
echo Starting TiTiler service...
echo Access API docs at: http://127.0.0.1:8000/docs
echo.
echo TiTiler will run in this window. Keep it open.
echo To stop TiTiler, close this window or press Ctrl+C.
echo.

:: --- Key Change: Use CALL and ensure PAUSE happens ---
:: Start TiTiler (adjust the module/script name if needed)
call python start_titiler.py

:: --- Always pause at the end, even if python command fails ---
echo.
echo ============================================================
echo  TITILER PROCESS FINISHED OR STOPPED
echo ============================================================
echo If you see this immediately, check the output above for errors.
echo If the window closes too quickly, copy the text or take a screenshot.
echo.
pause