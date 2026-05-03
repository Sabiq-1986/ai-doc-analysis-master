@echo off
REM =============================================================================
REM build_base_image.bat - Build the offline base Docker image
REM =============================================================================
REM Run from the app\ directory after download_wheels.bat.
REM =============================================================================

set SCRIPT_DIR=%~dp0
REM Remove trailing backslash for clean path handling
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

if not exist "%SCRIPT_DIR%\packages" (
    echo ERROR: packages\ is empty. Run download_wheels.bat first.
    pause
    exit /b 1
)

echo Building ragdoc-app-base:latest ...
docker build -f "%SCRIPT_DIR%\Dockerfile.base" -t ragdoc-app-base:latest "%SCRIPT_DIR%"

if %ERRORLEVEL% neq 0 (
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Done! Base image: ragdoc-app-base:latest
echo.
echo Next (from project root):
echo   docker-compose build app
echo   docker-compose up -d
echo.

set /p SAVE="Save image as .tar for offline transfer? [y/N]: "
if /i "%SAVE%"=="y" (
    docker save -o "%SCRIPT_DIR%\ragdoc-app-base-latest.tar" ragdoc-app-base:latest
    echo Saved: ragdoc-app-base-latest.tar
    echo Load on offline machine: docker load -i ragdoc-app-base-latest.tar
)

pause