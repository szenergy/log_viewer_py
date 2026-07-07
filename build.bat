@echo off
echo =============================================
echo   SZEnergy Log Viewer Build Script (Windows) 
echo =============================================

:: Check if python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python and try again.
    pause
    exit /b
)

:: 1. Activate or create virtual environment
if exist .venv (
    echo Activating existing virtual environment (.venv)...
    call .venv\Scripts\activate
) else (
    echo Creating new virtual environment (.venv)...
    python -m venv .venv
    call .venv\Scripts\activate
    echo Installing application dependencies...
    if exist requirements.txt (
        pip install -r requirements.txt
    ) else (
        pip install PySide6 pyqtgraph numpy pandas openpyxl npTDMS
    )
)

:: 2. Ensure PyInstaller is installed
echo Ensuring PyInstaller is installed...
pip install pyinstaller

:: 3. Build standalone executable
echo Building standalone Windows application...
pyinstaller --clean ^
            --onefile ^
            --windowed ^
            --icon=szenergy_logo.ico ^
            --name="SZEnergy Log Viewer" ^
            main.py

echo.
echo =============================================
echo               Build Complete!                
echo =============================================
echo Your single executable is located in:
echo   %cd%\dist\SZEnergy Log Viewer.exe
echo =============================================
pause
