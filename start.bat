@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    py -m venv .venv
    if errorlevel 1 goto error
)

.venv\Scripts\python.exe -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo Installing PySide6 for the first run...
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 goto error
)

.venv\Scripts\python.exe main.py
if errorlevel 1 goto error
exit /b 0

:error
echo.
echo Couldn't start PNG Wanderer. Check Python installation and the error above.
pause
exit /b 1
