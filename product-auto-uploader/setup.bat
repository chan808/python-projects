@echo off
cd /d "%~dp0"
echo ===== Product Auto Uploader Setup =====
echo.

python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Please install Python 3.9+ from https://www.python.org/downloads
    pause
    exit /b 1
)

echo [1/2] Installing packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

echo.
echo [2/2] Installing Chromium browser (first time only, may take a few minutes)...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] playwright install failed.
    pause
    exit /b 1
)

echo.
echo Setup complete! Double-click run.bat to start the program.
echo.
pause
