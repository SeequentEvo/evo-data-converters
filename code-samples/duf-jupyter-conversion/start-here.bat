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

call :WarnIfLongPathRisk

REM Allow forcing pip setup via any argument, e.g. start-here.bat --force-pip
for %%I in (%*) do (
    if /i "%%~I"=="--force-pip" set "FORCE_PIP_SETUP=1"
)

REM Normalize possible quoted values from environment assignment
set "FORCE_PIP_SETUP=!FORCE_PIP_SETUP:\"=!"

if /i "!FORCE_PIP_SETUP!"=="1" (
    echo FORCE_PIP_SETUP=1 detected. Skipping uv setup and using pip setup...
    echo.
    call :PipSetup
    if errorlevel 1 (
        echo.
        echo ERROR: Forced pip setup failed.
        pause
        exit /b 1
    )
) else (
    call :TryUvSetup
    if errorlevel 1 (
        echo.
        echo uv setup failed. Falling back to pip setup...
        echo.
        call :PipSetup
        if errorlevel 1 (
            echo.
            echo ERROR: pip fallback setup failed after uv setup failed.
            pause
            exit /b 1
        )
    )
)

call :LaunchNotebook
exit /b %ERRORLEVEL%

:WarnIfLongPathRisk
set "LONG_PATHS_STATE=unknown"
set "LONG_PATHS_VALUE="

for /f "tokens=3" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled 2^>nul ^| find "LongPathsEnabled"') do (
    set "LONG_PATHS_VALUE=%%A"
)

if /i "!LONG_PATHS_VALUE!"=="0x1" set "LONG_PATHS_STATE=enabled"
if /i "!LONG_PATHS_VALUE!"=="0x0" set "LONG_PATHS_STATE=disabled"

set "RISK_PATH=%SCRIPT_DIR%.venv\Lib\site-packages\evo_schemas\schema\objects\non-parametric-continuous-cumulative-distribution\1.0.1\non-parametric-continuous-cumulative-distribution.schema.json"
call :StrLen RISK_PATH RISK_PATH_LENGTH

if /i "!LONG_PATHS_STATE!"=="disabled" (
    if !RISK_PATH_LENGTH! geq 260 (
        echo WARNING: Windows Long Path support appears to be disabled.
        echo WARNING: This folder path is long enough that package installation may fail.
        echo WARNING: Enable Long Paths in Windows or move this project closer to the drive root.
        echo WARNING: Current projected install path length: !RISK_PATH_LENGTH! characters.
        echo.
    )
)

if /i "!LONG_PATHS_STATE!"=="unknown" (
    if !RISK_PATH_LENGTH! geq 260 (
        echo WARNING: Could not determine whether Windows Long Path support is enabled.
        echo WARNING: This folder path is long enough that package installation may fail.
        echo WARNING: If setup fails, enable Long Paths in Windows or move this project closer to the drive root.
        echo WARNING: Current projected install path length: !RISK_PATH_LENGTH! characters.
        echo.
    )
)

exit /b 0

:TryUvSetup
set "UV_WAS_INSTALLED=0"
where uv >nul 2>&1
if !ERRORLEVEL! equ 0 (
    set "UV_WAS_INSTALLED=1"
)

if !ERRORLEVEL! neq 0 (
    echo uv not found. Installing...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo ERROR: Failed to install uv.
        exit /b 1
    )
    
    REM Refresh PATH to pick up newly installed uv
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
    
    REM Verify uv is now available
    where uv >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo ERROR: Failed to install uv.
        echo Please install manually: https://github.com/astral-sh/uv
        exit /b 1
    )
    echo uv installed successfully!
)

REM Try upgrading uv to latest if it was already installed
if %UV_WAS_INSTALLED% equ 1 (
    echo Updating uv to latest...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" >nul 2>&1
)

echo Setting up virtual environment with uv...
echo.
pushd "%SCRIPT_DIR%"
if errorlevel 1 (
    echo ERROR: Failed to enter script directory.
    exit /b 1
)
uv sync
if errorlevel 1 (
    popd
    echo ERROR: uv sync failed.
    exit /b 1
)
popd
echo.
echo uv setup completed successfully!
echo.

exit /b 0

:PipSetup
REM Find a Python launcher/interpreter that can create the virtual environment
set "PYTHON_CMD="
set "PYTHON_PREFERRED_VERSION="
set "ROOT_PYTHON_VERSION_FILE=%SCRIPT_DIR%..\..\.python-version"

if defined ROOT_PYTHON_VERSION_FILE if exist "!ROOT_PYTHON_VERSION_FILE!" (
    for /f "usebackq tokens=1 delims= " %%V in ("!ROOT_PYTHON_VERSION_FILE!") do set "PYTHON_PREFERRED_VERSION=%%V"
    for /f "tokens=1,2,3 delims=." %%A in ("!PYTHON_PREFERRED_VERSION!") do (
        if not "%%A"=="" if not "%%B"=="" set "PYTHON_PREFERRED_VERSION=%%A.%%B"
    )
    echo Found repo Python version preference: !PYTHON_PREFERRED_VERSION!
)

where py >nul 2>&1
if !ERRORLEVEL! equ 0 (
    if defined PYTHON_PREFERRED_VERSION (
        py -!PYTHON_PREFERRED_VERSION! --version >nul 2>&1
        if !ERRORLEVEL! equ 0 set "PYTHON_CMD=py -!PYTHON_PREFERRED_VERSION!"
    )

    py -3.12 --version >nul 2>&1
    if !ERRORLEVEL! equ 0 if not defined PYTHON_CMD set "PYTHON_CMD=py -3.12"

    if not defined PYTHON_CMD (
        py -3.11 --version >nul 2>&1
        if !ERRORLEVEL! equ 0 set "PYTHON_CMD=py -3.11"
    )

    if not defined PYTHON_CMD (
        py -3.10 --version >nul 2>&1
        if !ERRORLEVEL! equ 0 set "PYTHON_CMD=py -3.10"
    )
)

if not defined PYTHON_CMD (
    where python >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        python -c "import sys; pref='!PYTHON_PREFERRED_VERSION!'.strip(); v=f'{sys.version_info[0]}.{sys.version_info[1]}'; ok=((3, 10) <= sys.version_info[:2] <= (3, 12)) and ((not pref) or (v == pref)); raise SystemExit(0 if ok else 1)" >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            set "PYTHON_CMD=python"
        ) else (
            if defined PYTHON_PREFERRED_VERSION (
                echo ERROR: Found python in PATH, but it is not the preferred version !PYTHON_PREFERRED_VERSION! from .python-version.
            ) else (
                echo ERROR: Found python in PATH, but it is not Python 3.10 to 3.12.
            )
        )
    )
)

if not defined PYTHON_CMD (
    echo ERROR: Python 3.10 to 3.12 was not found.
    echo Please install Python from https://www.python.org/downloads/windows/
    exit /b 1
)

REM Check if virtual environment exists, if not create it
if not exist "%SCRIPT_DIR%.venv\" (
    echo Virtual environment not found. Creating it with %PYTHON_CMD%...
    echo.
    %PYTHON_CMD% -m venv "%SCRIPT_DIR%.venv"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        exit /b 1
    )
    echo.
    echo Virtual environment created successfully!
    echo.
)

REM Activate the local virtual environment
echo Activating virtual environment...
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    exit /b 1
)

REM Bootstrap pip if it is missing from this virtual environment
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo pip is missing in this virtual environment. Bootstrapping with ensurepip...
    python -m ensurepip --upgrade
    if errorlevel 1 (
        echo ERROR: Failed to bootstrap pip with ensurepip.
        exit /b 1
    )
)

REM Install or update dependencies with pip
echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip.
    exit /b 1
)

echo Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    exit /b 1
)

exit /b 0

:LaunchNotebook

REM Activate the local virtual environment
echo Activating virtual environment...
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Launch JupyterLab with the notebook
jupyter notebook "convert_duf.ipynb"
set "JUPYTER_EXIT_CODE=%ERRORLEVEL%"

REM Keep window open if there's an error
if %JUPYTER_EXIT_CODE% neq 0 (
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

exit /b %JUPYTER_EXIT_CODE%

:StrLen
set "%~2=0"
set "STRLEN_VALUE=!%~1!"

if not defined STRLEN_VALUE exit /b 0

:StrLenLoop
if defined STRLEN_VALUE (
    set "STRLEN_VALUE=!STRLEN_VALUE:~1!"
    set /a %~2+=1
    goto StrLenLoop
)

exit /b 0
