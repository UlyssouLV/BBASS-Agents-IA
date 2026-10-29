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
        } catch {
            # Backend pas encore à l'écoute : nouvel essai dans une seconde.
            Write-Verbose "Pas encore de réponse sur ${url} : $($_.Exception.Message)"
        }
        Start-Sleep -Seconds 1
    }
    if ($lanceur.HasExited) { throw "BBASS.exe s'est arrêté (code $($lanceur.ExitCode)) avant que le backend réponde." }
    if (-not $repond) { throw "Le backend n'a pas répondu sur $url en $DelaiSecondes s." }
    Write-Host "OK : le paquet démarre et répond sur $url"
    if ((Backends).Count -eq 0) { throw "Aucun processus poste-backend : qui a répondu sur $url ?" }

    # Instance unique : un second BBASS.exe rouvre la fenêtre du premier et s'arrête.
    $second = Start-Process -FilePath (Join-Path $Paquet "BBASS.exe") -PassThru
    if (-not $second.WaitForExit(15000)) {
        Stop-Process -Id $second.Id -Force
        throw "Un second BBASS.exe est resté lancé (instance unique)."
    }
    if ($lanceur.HasExited) { throw "Le premier BBASS.exe s'est arrêté au second lancement." }
    if ((Backends).Count -ne 1) { throw "Un second lancement a démarré un autre poste-backend." }
    Write-Host "OK : un second lancement ne démarre ni second Lanceur ni second backend"

    $journaux = Join-Path $env:LOCALAPPDATA "BBASS\journaux"
    foreach ($journal in "lanceur.log", "poste-backend.log") {
        if (-not (Test-Path (Join-Path $journaux $journal))) { throw "Journal absent : $journaux\$journal" }
    }
    Write-Host "OK : journaux du Lanceur et du backend dans $journaux"

    # Sans Serveur BBASS joignable ici : vérification en échec, démarrage sur la version du paquet.
    $etat = Join-Path $env:LOCALAPPDATA "BBASS\mise-a-jour.json"
    if (-not (Test-Path $etat)) { throw "Fichier d'état de la mise à jour absent : $etat" }
    $verification = Get-Content $etat -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "OK : fichier d'état écrit ($($verification.resultat))"
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
