#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "======================================"
echo "   SZEnergy Log Viewer Build Script   "
echo "======================================"

# 1. Activate virtual environment
if [ -d ".venv" ]; then
    echo "Activating existing virtual environment (.venv)..."
    source .venv/bin/activate
else
    echo "Creating new virtual environment (.venv)..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "Installing application dependencies..."
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        pip install PySide6 pyqtgraph numpy pandas openpyxl npTDMS
    fi
fi

# 2. Ensure PyInstaller is installed
echo "Ensuring PyInstaller is installed..."
pip install pyinstaller

# 3. Build standalone executable
echo "Building standalone Linux application..."
pyinstaller --clean \
            --onefile \
            --windowed \
            --icon=szenergy_logo.ico \
            --name="SZEnergy Log Viewer" \
            main.py

echo ""
echo "============================================="
echo "               Build Complete!               "
echo "============================================="
echo "Your single executable is located in:"
echo "  $(pwd)/dist/SZEnergy Log Viewer"
echo "============================================="
