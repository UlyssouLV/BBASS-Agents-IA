@echo off
rem Trouve uv sur le PATH, ou dans le dossier d'installation par defaut, ou
rem l'installe (script officiel Astral). Pas de setlocal : le PATH enrichi
rem doit survivre au call depuis preparer-package / les lanceurs.

where uv >nul 2>nul
if not errorlevel 1 exit /b 0

if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    exit /b 0
)

if exist "%USERPROFILE%\.cargo\bin\uv.exe" (
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
    exit /b 0
)

echo       uv n'est pas installe : installation ^(script officiel Astral^)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 (
    echo [ERREUR] Echec de l'installation de uv.
    echo          Installe-le a la main ^(voir README.md, section Prerequis^), puis relance ce script.
    exit /b 1
)

if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] uv a ete installe mais n'est pas encore sur le PATH de cette fenetre.
    echo          Ferme cette fenetre, relance le script. Si ca persiste, vois README.md ^(Prerequis^).
    exit /b 1
)

exit /b 0
