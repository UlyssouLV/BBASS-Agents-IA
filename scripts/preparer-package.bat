@echo off
rem Prepare un package Python (venv + dependances + .env) avant de le lancer.
rem Usage : call scripts\preparer-package.bat "chemin\vers\le\package"
rem Le package doit contenir un uv.lock (source de verite des versions installees) ;
rem uv resout la version de Python via son propre .python-version (3.11).
setlocal
set "PKG_DIR=%~1"

uv --version >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] "uv" est requis mais n'a pas ete trouve sur le PATH.
    echo          Installe-le ^(voir README.md, section Prerequis^), puis relance ce script.
    exit /b 1
)

if not exist "%PKG_DIR%\pyproject.toml" (
    echo [ERREUR] "%PKG_DIR%" ne contient pas de pyproject.toml.
    exit /b 1
)

if not exist "%PKG_DIR%\uv.lock" (
    echo [ERREUR] "%PKG_DIR%" ne contient pas de uv.lock.
    exit /b 1
)

if not exist "%PKG_DIR%\.env" (
    if exist "%PKG_DIR%\.env.example" (
        echo       Creation de "%PKG_DIR%\.env" a partir de .env.example...
        copy /y "%PKG_DIR%\.env.example" "%PKG_DIR%\.env" >nul
    )
)

echo       Installation des dependances ^(uv sync, versions figees par uv.lock^) dans "%PKG_DIR%\.venv"...
uv sync --directory "%PKG_DIR%" --extra test --python 3.11 --locked
if errorlevel 1 (
    echo [ERREUR] Echec de l'installation des dependances pour "%PKG_DIR%".
    echo          Verifie ta connexion internet et le message uv ci-dessus, puis relance ce script.
    exit /b 1
)

exit /b 0
