# Test de fumée du paquet poste : BBASS.exe démarre le backend, qui répond sur
# 127.0.0.1:8100 ; tuer le Lanceur ne laisse pas de backend orphelin.
# Usage, après construire-paquet.ps1 :
#   powershell -ExecutionPolicy Bypass -File lanceur\scripts\test-fumee.ps1
param(
    [string]$Paquet = (Join-Path $PSScriptRoot "..\target\paquet\BBASS"),
    [int]$DelaiSecondes = 120
)

$ErrorActionPreference = "Stop"
$url = "http://127.0.0.1:8100/"

function Backends { @(Get-Process -Name "poste-backend" -ErrorAction SilentlyContinue) }

if ((Backends).Count -gt 0) { throw "Un poste-backend tourne déjà : arrêtez-le avant le test de fumée." }

$lanceur = Start-Process -FilePath (Join-Path $Paquet "BBASS.exe") -PassThru
try {
    $fin = (Get-Date).AddSeconds($DelaiSecondes)
    $repond = $false
    while ((Get-Date) -lt $fin -and -not $lanceur.HasExited) {
        try {
            $reponse = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($reponse.StatusCode -eq 200 -and $reponse.Content -match "<div id=`"root`">") { $repond = $true; break }
        } catch { }
        Start-Sleep -Seconds 1
    }
    if ($lanceur.HasExited) { throw "BBASS.exe s'est arrêté (code $($lanceur.ExitCode)) avant que le backend réponde." }
    if (-not $repond) { throw "Le backend n'a pas répondu sur $url en $DelaiSecondes s." }
    Write-Host "OK : le paquet démarre et répond sur $url"
    if ((Backends).Count -eq 0) { throw "Aucun processus poste-backend : qui a répondu sur $url ?" }
} finally {
    # Arrêt brutal : seul le Job Object du Lanceur peut alors emporter le backend.
    if (-not $lanceur.HasExited) { Stop-Process -Id $lanceur.Id -Force }
}

$fin = (Get-Date).AddSeconds(15)
while ((Backends).Count -gt 0 -and (Get-Date) -lt $fin) { Start-Sleep -Milliseconds 500 }
$orphelins = Backends
if ($orphelins.Count -gt 0) {
    $orphelins | Stop-Process -Force
    throw "poste-backend a survécu au Lanceur (processus orphelin)."
}
Write-Host "OK : arrêter le Lanceur arrête le backend (pas d'orphelin)"
