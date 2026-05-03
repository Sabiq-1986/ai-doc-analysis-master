@echo off
REM =============================================================================
REM download_wheels.bat - Download Python wheels for offline Docker build
REM =============================================================================
REM Run ONCE while online, from the app\ directory.
REM =============================================================================

echo =============================================
echo   RagDoc App - Offline Wheels Downloader
echo =============================================
echo.

set SCRIPT_DIR=%~dp0
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

set PACKAGES_DIR=%SCRIPT_DIR%\packages
set REQUIREMENTS_FILE=%SCRIPT_DIR%\..\requirements.txt

if not exist "%REQUIREMENTS_FILE%" (
    echo ERROR: requirements.txt not found at project root!
    pause
    exit /b 1
)

if exist "%PACKAGES_DIR%" rmdir /s /q "%PACKAGES_DIR%"
mkdir "%PACKAGES_DIR%"
copy "%REQUIREMENTS_FILE%" "%PACKAGES_DIR%\requirements.txt" >nul

REM -------------------------------------------------------------------
REM Step 1: Download torch CPU wheel (no deps - from PyTorch index)
REM -------------------------------------------------------------------
echo [1/3] Downloading torch CPU wheel from PyTorch index...
echo       (CPU-only ~300MB, no dependencies)
echo.

pip download ^
    --dest "%PACKAGES_DIR%" ^
    --platform manylinux_2_28_x86_64 ^
    --python-version 3.12 ^
    --only-binary=:all: ^
    --no-deps ^
    "torch>=2.2.0" ^
    --index-url https://download.pytorch.org/whl/cpu

if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to download torch CPU wheel!
    pause
    exit /b 1
)
echo   torch downloaded.
echo.

REM -------------------------------------------------------------------
REM Step 2: Download torch dependencies from PyPI
REM -------------------------------------------------------------------
echo [2/3] Downloading torch dependencies from PyPI...
echo.

pip download ^
    --dest "%PACKAGES_DIR%" ^
    --platform manylinux_2_17_x86_64 ^
    --platform manylinux2014_x86_64 ^
    --platform any ^
    --python-version 3.12 ^
    --only-binary=:all: ^
    filelock typing-extensions sympy networkx jinja2 fsspec MarkupSafe mpmath

if %ERRORLEVEL% neq 0 (
    echo WARNING: Some torch dependencies may have failed.
)
echo   torch dependencies downloaded.
echo.

REM -------------------------------------------------------------------
REM Step 3: Download onnxruntime separately (special handling)
REM -------------------------------------------------------------------
echo [3/4] Downloading onnxruntime for Linux x86_64...
echo       (This package requires special handling - direct PyPI download)
echo.

REM onnxruntime doesn't support cross-platform pip download
REM Download directly from PyPI using PowerShell
set ONNX_URL=https://files.pythonhosted.org/packages/ef/88/9cc25d2bafe6bc0d4d3c1db3ade98196d5b355c0b273e6a5dc09c5d5d0d5/onnxruntime-1.23.2-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
set ONNX_FILE=onnxruntime-1.23.2-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl

powershell -Command "& {$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%ONNX_URL%' -OutFile '%PACKAGES_DIR%\%ONNX_FILE%'}"

if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to download onnxruntime!
    echo        You may need to download manually from:
    echo        %ONNX_URL%
    pause
    exit /b 1
)

echo   onnxruntime downloaded (17.4 MB).
echo.

REM -------------------------------------------------------------------
REM Step 4: Download all other packages with dependencies
REM -------------------------------------------------------------------
echo [4/4] Downloading all other packages for Linux x86_64...
echo       This may take a few minutes...
echo.

REM Create requirements without torch and onnxruntime (already downloaded)
REM Using two findstr passes since findstr doesn't support multiple patterns well
findstr /v /i /b "torch" "%REQUIREMENTS_FILE%" | findstr /v /i /b "onnxruntime" > "%PACKAGES_DIR%\_remaining.txt"

pip download ^
    --dest "%PACKAGES_DIR%" ^
    --platform manylinux_2_17_x86_64 ^
    --platform manylinux2014_x86_64 ^
    --platform linux_x86_64 ^
    --platform any ^
    --python-version 3.12 ^
    --only-binary=:all: ^
    -r "%PACKAGES_DIR%\_remaining.txt"

if %ERRORLEVEL% neq 0 (
    echo.
    echo WARNING: Some packages may not have binary wheels.
    echo          Trying with source distributions allowed...
    echo.
    pip download ^
        --dest "%PACKAGES_DIR%" ^
        --platform manylinux_2_17_x86_64 ^
        --platform manylinux2014_x86_64 ^
        --platform linux_x86_64 ^
        --platform any ^
        --python-version 3.12 ^
        -r "%PACKAGES_DIR%\_remaining.txt"
)

del "%PACKAGES_DIR%\_remaining.txt" 2>nul

echo.
echo =============================================
echo   Download Complete!
echo =============================================
echo   Location: %PACKAGES_DIR%
echo   Torch:    CPU-only (no CUDA dependencies)
echo.
echo Next: build the base image:
echo   docker build -f Dockerfile.base -t ragdoc-app-base:latest .
echo.
pause
