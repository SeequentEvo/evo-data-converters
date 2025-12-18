REM  Copyright © 2025 Bentley Systems, Incorporated
REM  Licensed under the Apache License, Version 2.0 (the "License");
REM  you may not use this file except in compliance with the License.
REM  You may obtain a copy of the License at
REM      http://www.apache.org/licenses/LICENSE-2.0
REM  Unless required by applicable law or agreed to in writing, software
REM  distributed under the License is distributed on an "AS IS" BASIS,
REM  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
REM  See the License for the specific language governing permissions and
REM  limitations under the License.

@echo off
REM Batch script to publish DUF files to Evo
REM Usage: convert_duf.bat
REM Note: DUF file path is read from DUF_FILE_PATH in .env file

REM Set log file path
set "LOG_FILE=%~dp0log.txt"

REM Start logging (append to existing file, create if not exists)
echo. >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
echo [%DATE% %TIME%] Convert DUF Log >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
REM Also log the command line
echo [%DATE% %TIME%] Command: %0 %* >> "%LOG_FILE%"

REM Show startup message to console
echo.
echo ========================================
echo Starting DUF Conversion Process
echo ========================================
echo.

REM Call main function
call :main %*
goto :eof

:main
setlocal enabledelayedexpansion

REM Helper function to log to both console and file
REM Usage: call :log "message"
goto :skip_log_function
:log
set "msg=%~1"
echo %msg%
echo %msg% >> "%LOG_FILE%"
goto :eof
:skip_log_function

REM Load environment variables from .env file
set "ENV_FILE=%~dp0.env"
call :log "[%DATE% %TIME%] Checking for .env file..."
if not exist "%ENV_FILE%" (
    call :log "[%DATE% %TIME%] ERROR: .env file not found at "%ENV_FILE%""
    call :log "[%DATE% %TIME%] Please create a .env file with DUF_FILE_PATH variable."
    exit /b 1
)

call :log "[%DATE% %TIME%] Found .env file"
call :log "[%DATE% %TIME%] Loading environment variables from .env file..."
for /f "usebackq tokens=1,* delims==" %%a in ("%ENV_FILE%") do (
    set "line=%%a"
    REM Skip empty lines and comments
    if not "!line!"=="" (
        if not "!line:~0,1!"=="#" (
            set "%%a=%%b"
            call :log "[%DATE% %TIME%] Loaded: %%a"
        )
    )
)

REM Check if DUF_FILE_PATH is set
if not defined DUF_FILE_PATH (
    call :log "[%DATE% %TIME%] ERROR: DUF_FILE_PATH not found in .env file"
    call :log "[%DATE% %TIME%] Please add DUF_FILE_PATH to your .env file."
    exit /b 1
)

call :log "[%DATE% %TIME%] Successfully loaded DUF_FILE_PATH from .env"
call :log ""

REM Use DUF_FILE_PATH from .env file
REM Remove any leading/trailing quotes and spaces from DUF_FILE_PATH
set "SOURCE_FILE=%DUF_FILE_PATH%"
set "SOURCE_FILE=%SOURCE_FILE:"=%"
for %%F in ("%SOURCE_FILE%") do set "FILENAME=%%~nxF"

REM Set destination variables
set "DEST_DIR=%~dp0temp"
set "DEST_FILE=%DEST_DIR%\%FILENAME%"

call :log ""
call :log "[%DATE% %TIME%] ========================================"
call :log "[%DATE% %TIME%] Publish DUF to Evo Script"
call :log "[%DATE% %TIME%] ========================================"
call :log "[%DATE% %TIME%] Source: %SOURCE_FILE%"
call :log "[%DATE% %TIME%] Destination: %DEST_FILE%"
call :log ""

REM Check if source file exists
call :log "[%DATE% %TIME%] Verifying source file exists..."
call :log "[%DATE% %TIME%] Checking path: %SOURCE_FILE%"
if not exist "%SOURCE_FILE%" (
    call :log "[%DATE% %TIME%] ERROR: Source file does not exist"
    call :log "[%DATE% %TIME%] Please check the network path and filename in DUF_FILE_PATH."
    exit /b 1
)
call :log "[%DATE% %TIME%] Source file verified - file exists"
call :log ""

REM Check if destination directory exists, create if needed
if not exist "%DEST_DIR%" (
    call :log "[%DATE% %TIME%] Creating destination directory: "%DEST_DIR%""
    mkdir "%DEST_DIR%"
    if %ERRORLEVEL% neq 0 (
        call :log "[%DATE% %TIME%] ERROR: Failed to create destination directory: "%DEST_DIR%""
        call :log "[%DATE% %TIME%] Please check permissions."
        exit /b 1
    )
    call :log "[%DATE% %TIME%] Directory created successfully."
)

REM Check if destination file already exists
if exist "%DEST_FILE%" (
    call :log "[%DATE% %TIME%] WARNING: Destination file already exists - will overwrite"
    del "%DEST_FILE%" >nul 2>&1
    if exist "%DEST_FILE%" (
        call :log "[%DATE% %TIME%] WARNING: Could not delete existing file, will attempt to overwrite"
    )
)

REM Copy the file
call :log "[%DATE% %TIME%] Copying file from source to temp folder..."
call :log "[%DATE% %TIME%] This may take a moment for large files..."
copy /Y "%SOURCE_FILE%" "%DEST_FILE%" >nul

if %ERRORLEVEL% equ 0 (
    call :log ""
    call :log "[%DATE% %TIME%] SUCCESS: File copied successfully!"
    call :log "[%DATE% %TIME%] File is now available at: %DEST_FILE%"
) else (
    call :log ""
    call :log "[%DATE% %TIME%] ERROR: Failed to copy file. Error code: %ERRORLEVEL%"
    call :log "[%DATE% %TIME%] Please check network connectivity and file permissions."
    call :log "[%DATE% %TIME%] WARNING: Continuing anyway, but Python script may fail..."
)

call :log ""
REM Run publish_to_evo.py after copying is complete
call :log "[%DATE% %TIME%] ========================================"
call :log "[%DATE% %TIME%] Starting Evo Publishing Process"
call :log "[%DATE% %TIME%] ========================================"
call :log "[%DATE% %TIME%] Running publish_to_evo.py..."
call :log "[%DATE% %TIME%] This may take several minutes depending on file size..."
call :log ""

REM Check if uv is installed
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    call :log "[%DATE% %TIME%] ERROR: uv not found in PATH"
    call :log "[%DATE% %TIME%] Please install uv: https://github.com/astral-sh/uv"
    call :log "[%DATE% %TIME%] Run: pip install uv"
    exit /b 1
)

REM Check if publish_to_evo.py exists
if not exist "%~dp0publish_to_evo.py" (
    call :log "[%DATE% %TIME%] ERROR: publish_to_evo.py not found"
    call :log "[%DATE% %TIME%] Expected location: %~dp0publish_to_evo.py"
    exit /b 1
)

REM Validate required environment variables are set
call :log "[%DATE% %TIME%] Validating environment variables..."
set "MISSING_VARS="

if not defined EVO_ORG_ID set "MISSING_VARS=%MISSING_VARS% EVO_ORG_ID"
if not defined EVO_WORKSPACE_ID set "MISSING_VARS=%MISSING_VARS% EVO_WORKSPACE_ID"
if not defined EVO_CLIENT_ID set "MISSING_VARS=%MISSING_VARS% EVO_CLIENT_ID"
if not defined EVO_CLIENT_SECRET set "MISSING_VARS=%MISSING_VARS% EVO_CLIENT_SECRET"
if not defined EVO_HUB_URL set "MISSING_VARS=%MISSING_VARS% EVO_HUB_URL"
if not defined EVO_USER_AGENT set "MISSING_VARS=%MISSING_VARS% EVO_USER_AGENT"
if not defined EVO_EPSG_CODE set "MISSING_VARS=%MISSING_VARS% EVO_EPSG_CODE"

if not "%MISSING_VARS%"=="" (
    call :log "[%DATE% %TIME%] ERROR: Missing required environment variables:%MISSING_VARS%"
    call :log "[%DATE% %TIME%] Please ensure your .env file contains all required variables."
    exit /b 1
)

call :log "[%DATE% %TIME%] All required environment variables are set."

REM Set upload path with default empty string if not defined
if not defined EVO_UPLOAD_PATH set "EVO_UPLOAD_PATH="

REM Run the Python script with all parameters and log output
echo Running Python script... >> "%LOG_FILE%"
uv run "%~dp0publish_to_evo.py" --duf-file "%DEST_FILE%" --org-id "%EVO_ORG_ID%" --workspace-id "%EVO_WORKSPACE_ID%" --client-id "%EVO_CLIENT_ID%" --client-secret "%EVO_CLIENT_SECRET%" --hub-url "%EVO_HUB_URL%" --user-agent "%EVO_USER_AGENT%" --epsg-code "%EVO_EPSG_CODE%" --upload-path "%EVO_UPLOAD_PATH%" --combine-layers 2>&1 | "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -Command "$input | ForEach-Object { Write-Output $_; Add-Content -Path '%LOG_FILE%' -Value $_ }"
set PYTHON_EXIT_CODE=%ERRORLEVEL%
echo Python script finished with exit code: %PYTHON_EXIT_CODE% >> "%LOG_FILE%"

if %PYTHON_EXIT_CODE% equ 0 (
    call :log ""
    call :log "[%DATE% %TIME%] Python script completed successfully."
) else (
    call :log ""
    call :log "[%DATE% %TIME%] WARNING: Python script exited with code: %PYTHON_EXIT_CODE%"
)

call :log ""
REM Clean up temp folder
call :log "[%DATE% %TIME%] Cleaning up temporary files..."
if exist "%DEST_DIR%" (
    rd /s /q "%DEST_DIR%" >nul 2>&1
    if exist "%DEST_DIR%" (
        call :log "[%DATE% %TIME%] WARNING: Could not delete temp folder: %DEST_DIR%"
    ) else (
        call :log "[%DATE% %TIME%] Temporary folder deleted successfully"
    )
) else (
    call :log "[%DATE% %TIME%] No temp folder to clean up"
)

call :log ""
call :log "[%DATE% %TIME%] ========================================"
call :log "[%DATE% %TIME%] Script execution completed."
call :log "[%DATE% %TIME%] ========================================"
call :log "[%DATE% %TIME%] Check log file for details: %LOG_FILE%"
exit /b
