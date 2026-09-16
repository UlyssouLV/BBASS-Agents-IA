@echo off
rem Prepare un package Python (venv + dependances + .env) avant de le lancer.
rem Usage : call scripts\preparer-package.bat "chemin\vers\le\package"
rem Necessite que PYTHON_CMD ait deja ete defini par scripts\verifier-python.bat.
setlocal
set "PKG_DIR=%~1"

if "%PYTHON_CMD%"=="" (
    echo [ERREUR interne] PYTHON_CMD n'est pas defini ^(verifier-python.bat doit etre appele avant^).
    exit /b 1
)

if not exist "%PKG_DIR%\pyproject.toml" (
    echo [ERREUR] "%PKG_DIR%" ne contient pas de pyproject.toml.
    exit /b 1
)

if not exist "%PKG_DIR%\.venv\Scripts\python.exe" (
    echo       Creation de l'environnement virtuel "%PKG_DIR%\.venv"...
    %PYTHON_CMD% -m venv "%PKG_DIR%\.venv"
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer l'environnement virtuel dans "%PKG_DIR%".
        exit /b 1
    )
)

if not exist "%PKG_DIR%\.env" (
    if exist "%PKG_DIR%\.env.example" (
        echo       Creation de "%PKG_DIR%\.env" a partir de .env.example...
        copy /y "%PKG_DIR%\.env.example" "%PKG_DIR%\.env" >nul
    )
)

echo       Installation des dependances ^(pip install -e^) dans "%PKG_DIR%\.venv"...
"%PKG_DIR%\.venv\Scripts\python.exe" -m pip install -e "%PKG_DIR%"
if errorlevel 1 (
    echo [ERREUR] Echec de l'installation des dependances pour "%PKG_DIR%".
    echo          Verifie ta connexion internet et le message pip ci-dessus, puis relance ce script.
    exit /b 1
)

exit /b 0
