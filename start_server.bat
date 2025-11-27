@echo off
echo ========================================
echo Iniciando LabVotoAI Backend
echo ========================================
echo.

REM Verificar se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado!
    echo.
    echo Por favor, instale o Python 3.8 ou superior:
    echo https://www.python.org/downloads/
    echo.
    echo Ou use o comando: python3 --version
    pause
    exit /b 1
)

echo Python encontrado!
echo.

REM Verificar se as dependências estão instaladas
echo Verificando dependencias...
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERRO ao instalar dependencias!
        pause
        exit /b 1
    )
)

echo.
echo Iniciando servidor FastAPI...
echo.
echo Acesse: http://localhost:8000/docs
echo.
echo Pressione Ctrl+C para parar o servidor
echo.

python run.py

pause




