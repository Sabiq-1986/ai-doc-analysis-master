@echo off
REM =============================================================================
REM download_models.bat - Download HuggingFace models for offline use
REM =============================================================================
REM Run ONCE while online to download sentence-transformer models.
REM Models will be saved to the models/ directory.
REM =============================================================================

echo =============================================
echo   RagDoc - Offline Models Downloader
echo =============================================
echo.

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%\.."

set MODELS_DIR=%CD%\models

echo Downloading multilingual sentence-transformer model...
echo Target: %MODELS_DIR%
echo.

python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); model.save('%MODELS_DIR:\=/%/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Failed to download model!
    echo Make sure you have sentence-transformers installed:
    echo   pip install sentence-transformers
    pause
    exit /b 1
)

echo.
echo =============================================
echo   Model Downloaded Successfully!
echo =============================================
echo   Location: %MODELS_DIR%\sentence-transformers
echo.
echo For offline Docker deployment, the model will be
echo mounted at /app/models via docker-compose.yml
echo.
pause
