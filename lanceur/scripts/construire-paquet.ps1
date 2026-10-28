# Construit le paquet poste Windows dans lanceur\target\paquet\BBASS\ :
#   BBASS.exe                         Lanceur (Tauri)
#   poste-backend\poste-backend.exe   backend poste figé par PyInstaller (onedir)
#
# Prérequis : Node 20+, Python 3.11, Rust (MSVC) et WebView2 (présent dans Windows 10/11).
# Usage, depuis la racine du dépôt :
#   powershell -ExecutionPolicy Bypass -File lanceur\scripts\construire-paquet.ps1
param(
    # Interpréteur Python 3.11 qui crée l'environnement de construction du sidecar.
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$racine = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$lanceur = Join-Path $racine "lanceur"
$cible = Join-Path $lanceur "target"
$paquet = Join-Path $cible "paquet\BBASS"

function Executer([string]$Etape, [scriptblock]$Commande) {
    Write-Host "==> $Etape"
    & $Commande
    if ($LASTEXITCODE -ne 0) { throw "$Etape : échec (code $LASTEXITCODE)" }
}

Executer "Front du poste (npm run build)" {
    Push-Location (Join-Path $racine "poste\frontend")
    try { npm ci --ignore-scripts; if ($LASTEXITCODE -eq 0) { npm run build } } finally { Pop-Location }
}

$venv = Join-Path $cible "venv-sidecar"
$pythonVenv = Join-Path $venv "Scripts\python.exe"
Executer "Environnement Python du sidecar" { & $Python -m venv $venv }
# Installation non éditable : PyInstaller doit trouver poste\static dans le paquet installé.
Executer "Dépendances du sidecar" {
    & $pythonVenv -m pip install --disable-pip-version-check --quiet (Join-Path $racine "poste") "pyinstaller>=6.10,<7"
}

$travailPyInstaller = Join-Path $cible "pyinstaller"
Executer "Sidecar PyInstaller (onedir)" {
    & $pythonVenv -m PyInstaller --noconfirm --clean --onedir --console `
        --name poste-backend `
        --icon (Join-Path $lanceur "icons\icon.ico") `
        --distpath (Join-Path $cible "sidecar") `
        --workpath $travailPyInstaller `
        --specpath $travailPyInstaller `
        --collect-data poste `
        --collect-submodules uvicorn `
        --copy-metadata keyring `
        --hidden-import keyring.backends.Windows `
        (Join-Path $lanceur "sidecar\poste-backend.py")
}

Executer "Lanceur (cargo build --release)" {
    Push-Location $lanceur
    try { cargo build --release --locked -p bbass-lanceur } finally { Pop-Location }
}

Write-Host "==> Assemblage dans $paquet"
if (Test-Path $paquet) { Remove-Item -Recurse -Force $paquet }
New-Item -ItemType Directory -Force $paquet | Out-Null
Copy-Item (Join-Path $cible "release\BBASS.exe") $paquet
Copy-Item -Recurse (Join-Path $cible "sidecar\poste-backend") $paquet
Write-Host "Paquet prêt : $paquet\BBASS.exe"
