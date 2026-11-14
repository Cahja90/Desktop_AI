#prueft ob gitleaks da ist; install nur nach freigabe
param(
  [switch]$Installieren
)

$ErrorActionPreference = "Stop"

function teste_gitleaks {
  $cmd = Get-Command gitleaks -ErrorAction SilentlyContinue
  if ($cmd) {
    Write-Host "gitleaks gefunden: $($cmd.Source)"
    try {
      & gitleaks version
    } catch {
      Write-Host "gitleaks antwortet nicht auf version"
    }
    return $true
  }
  return $false
}

if (teste_gitleaks) {
  exit 0
}

Write-Host "gitleaks fehlt."
Write-Host "zum installieren (nur nach deinem ok):"
Write-Host "  powershell -NoProfile -File dev\gitleaks-pruefen.ps1 -Installieren"
Write-Host "oder:"
Write-Host "  winget install --id Gitleaks.Gitleaks -e"

if (-not $Installieren) {
  exit 1
}

Write-Host "starte winget install..."
winget install --id Gitleaks.Gitleaks -e --accept-package-agreements --accept-source-agreements
if ($LASTEXITCODE -ne 0) {
  Write-Host "winget install fehlgeschlagen"
  exit $LASTEXITCODE
}

if (teste_gitleaks) {
  exit 0
}
Write-Host "nach install immer noch nicht im pfad. terminal neu oeffnen."
exit 1
