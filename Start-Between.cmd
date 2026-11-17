@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "BETWEEN_PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
    set "BETWEEN_PYTHON=python"
)
"%BETWEEN_PYTHON%" -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Install the app dependencies using:
    echo "%BETWEEN_PYTHON%" -m pip install -r requirements.txt
    pause
    exit /b 1
)
"%BETWEEN_PYTHON%" -m ml.check
if errorlevel 1 echo Model setup needs attention. The app will still open and save answers.
"%BETWEEN_PYTHON%" app.py
pause
