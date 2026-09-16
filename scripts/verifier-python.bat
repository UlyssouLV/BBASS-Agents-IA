@echo off
rem Determine une commande Python 3.11 utilisable et l'expose dans PYTHON_CMD
rem pour le script appelant (pas de setlocal ici : la variable doit survivre au call).

py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.11"
    exit /b 0
)

python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)

echo [ERREUR] Python 3.11 est requis mais n'a pas ete trouve ^(ni "py -3.11", ni "python" en 3.11.x^).
echo          Installe Python 3.11.9 ^(voir README.md, section Prerequis^), coche "Add python.exe to PATH", puis relance ce script.
exit /b 1
