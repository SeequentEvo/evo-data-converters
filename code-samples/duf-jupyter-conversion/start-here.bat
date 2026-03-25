@echo off
setlocal EnableDelayedExpansion
echo Launching JupyterLab...
echo.

REM Get the directory where the batch file is located
set "SCRIPT_DIR=%~dp0"

REM Change to the script directory to ensure consistent file operations
cd /d "%SCRIPT_DIR%"
if errorlevel 1 (
    echo ERROR: Failed to change to script directory
    pause
    exit /b 1
)

REM Ensure uv is installed (install or upgrade if needed)
set "UV_WAS_INSTALLED=0"
where uv >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "UV_WAS_INSTALLED=1"
)

if %ERRORLEVEL% neq 0 (
    echo uv not found. Installing...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    
    REM Refresh PATH to pick up newly installed uv
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
    
    REM Verify uv is now available
    where uv >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo ERROR: Failed to install uv.
        echo Please install manually: https://github.com/astral-sh/uv
        pause
        exit /b 1
    )
    echo uv installed successfully!
)

REM Try upgrading uv to latest if it was already installed
if %UV_WAS_INSTALLED% equ 1 (
    echo Updating uv to latest...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" >nul 2>&1
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
jupyter notebook "convert_duf.ipynb"

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
