@echo off
REM start_titiler_simple.bat
REM A very simple script to start TiTiler

echo ============================================================
echo  STARTING TITILER (Simple Script)
echo ============================================================

REM --- 1. Navigate to the project directory ---
cd /d "C:\Users\Acer\mumbai-geo-ai-backend"
echo Current Directory: %cd%

REM --- 2. Check if the project directory seems correct ---
if not exist "start_titiler.py" (
    echo.
    echo ERROR: start_titiler.py not found in the current directory.
    echo Please make sure this script is in the correct project folder.
    echo.
    goto :error_pause
)

REM --- 3. Check if the virtual environment exists ---
if not exist "venv" (
    echo.
    echo ERROR: 'venv' folder not found. Please create your Python virtual environment first.
    echo.
    goto :error_pause
)

REM --- 4. Activate the virtual environment ---
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM --- 5. Check if activation was successful ---
if not defined VIRTUAL_ENV (
    echo.
    echo ERROR: Failed to activate the virtual environment.
    echo Make sure 'venv\Scripts\activate.bat' exists and is correct.
    echo.
    goto :error_pause
)
echo Virtual Environment Activated: %VIRTUAL_ENV%

REM --- 6. Set the PROJ_LIB environment variable ---
set PROJ_LIB=%cd%\venv\Lib\site-packages\rasterio\proj_data
echo PROJ_LIB set to: %PROJ_LIB%

REM --- 7. Inform user and start TiTiler ---
echo.
echo Starting TiTiler service...
echo Please wait, the server might take a moment to start.
echo Access API docs at: http://127.0.0.1:8000/docs (once started)
echo To stop TiTiler, close this window or press Ctrl+C.
echo ------------------------------------------------------------
echo.

REM --- 8. Run the TiTiler application ---
python start_titiler.py

REM --- 9. If execution reaches here, it means the python command finished ---
echo.
echo ------------------------------------------------------------
echo TiTiler process finished or was stopped.
echo ------------------------------------------------------------

:error_pause
echo.
echo Press any key to close this window...
pause >nul
exit /b 0