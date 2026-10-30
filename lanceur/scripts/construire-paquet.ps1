# Construit le paquet poste Windows dans lanceur\target\paquet\BBASS\ :
#   BBASS.exe                         Lanceur (Tauri)
#   poste-backend\poste-backend.exe   backend poste figé par PyInstaller (onedir)
#
# Prérequis : Node 20+, Python 3.11, Rust (MSVC) et WebView2 (présent dans Windows 10/11).
# Usage, depuis la racine du dépôt :
#   powershell -ExecutionPolicy Bypass -File lanceur\scripts\construire-paquet.ps1 [-Version X.Y.Z]
param(
    # Interpréteur Python 3.11 qui crée l'environnement de construction du sidecar.
    [string]$Python = "python",
    # Version annoncée par BBASS.exe (Release vX.Y.Z) ; sans elle, celle de lanceur\Cargo.toml.
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$racine = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$lanceur = Join-Path $racine "lanceur"
$cible = Join-Path $lanceur "target"
$paquet = Join-Path $cible "paquet\BBASS"

if ($Version -and $Version -notmatch '^\d+\.\d+\.\d+$') { throw "Version « $Version » : attendu X.Y.Z." }

function Executer([string]$Etape, [scriptblock]$Commande) {
    Write-Host "==> $Etape"
    & $Commande
    if ($LASTEXITCODE -ne 0) { throw "$Etape : échec (code $LASTEXITCODE)" }
}

Executer "Front du poste et assistant d'installation (npm run build, build:installateur)" {
    Push-Location (Join-Path $racine "poste\frontend")
    try {
        npm ci --ignore-scripts
        if ($LASTEXITCODE -eq 0) { npm run build }
        if ($LASTEXITCODE -eq 0) { npm run build:installateur }
    } finally { Pop-Location }
}

$venv = Join-Path $cible "venv-sidecar"
$pythonVenv = Join-Path $venv "Scripts\python.exe"
Executer "Environnement Python du sidecar" { & $Python -m venv $venv }
# Versions de poste\uv.lock, pas les dernières publiées : sans le lock, pip
# a pris pydantic 2.14 le 2026-10-30, que PyInstaller ne sait pas figer
# (« pydantic:compiled has been removed in V2 »).
$exigences = Join-Path $cible "exigences-sidecar.txt"
Executer "Versions verrouillées du sidecar (uv export)" {
    & $pythonVenv -m pip install --disable-pip-version-check --quiet "uv>=0.5,<1"
    if ($LASTEXITCODE -eq 0) {
        & $pythonVenv -m uv export --frozen --no-dev --no-emit-project --no-hashes --quiet `
            --project (Join-Path $racine "poste") --output-file $exigences
    }
}
# Installation non éditable : PyInstaller doit trouver poste\static dans le paquet installé.
Executer "Dépendances du sidecar" {
    & $pythonVenv -m pip install --disable-pip-version-check --quiet --requirement $exigences
    if ($LASTEXITCODE -eq 0) {
        & $pythonVenv -m pip install --disable-pip-version-check --quiet --no-deps (Join-Path $racine "poste")
    }
    if ($LASTEXITCODE -eq 0) {
        & $pythonVenv -m pip install --disable-pip-version-check --quiet "pyinstaller>=6.10,<7"
    }
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
    # Lu par tauri-build (ressource de version de l'exe) et generate_context! (build.rs).
    if ($Version) { $env:TAURI_CONFIG = (@{ version = $Version } | ConvertTo-Json -Compress) }
    try { cargo build --release --locked -p bbass-lanceur } finally { Remove-Item Env:TAURI_CONFIG -ErrorAction SilentlyContinue; Pop-Location }
}

if ($Version) {
    $annoncee = (Get-Item (Join-Path $cible "release\BBASS.exe")).VersionInfo.ProductVersion
    if ($annoncee -ne $Version) { throw "BBASS.exe annonce la version « $annoncee », attendu « $Version »." }
    Write-Host "BBASS.exe annonce la version $Version"
}

Write-Host "==> Assemblage dans $paquet"
if (Test-Path $paquet) { Remove-Item -Recurse -Force $paquet }
New-Item -ItemType Directory -Force $paquet | Out-Null
Copy-Item (Join-Path $cible "release\BBASS.exe") $paquet
Copy-Item -Recurse (Join-Path $cible "sidecar\poste-backend") $paquet
Write-Host "Paquet prêt : $paquet\BBASS.exe"
