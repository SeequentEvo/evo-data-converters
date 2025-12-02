@echo off
echo Launching JupyterLab...
echo File: %~1
echo.

REM Get the directory where the batch file is located
set "SCRIPT_DIR=%~dp0"

REM Check if uv is installed
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: uv not found in PATH
    echo Please install uv: https://github.com/astral-sh/uv
    echo Run: pip install uv
    echo.
    pause
    exit /b 1
)

REM Check if virtual environment exists, if not create it
if not exist "%SCRIPT_DIR%.venv\" (
    echo Virtual environment not found. Creating it with uv...
    echo.
    pushd "%SCRIPT_DIR%"
    uv sync
    popd
    echo.
    echo Virtual environment created successfully!
    echo.
)

REM Activate the local virtual environment
echo Activating virtual environment...
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"

REM Launch JupyterLab with the notebook
jupyter lab "%~1"

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo ERROR: JupyterLab failed to launch
    echo.
    echo Possible issues:
    echo - Jupyter is not installed
    echo - Jupyter is not in PATH
    echo - Wrong Python environment
    echo.
    pause
)
