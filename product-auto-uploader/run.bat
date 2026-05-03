@echo off
cd /d "%~dp0"

python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please run setup.bat first.
    pause
    exit /b 1
)

python -m app.main
if errorlevel 1 (
    echo.
    echo Program exited with an error.
    pause
)
