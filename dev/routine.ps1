#woechentliche pflege alles im modus vorschlagen
param(
  [string]$Hub = ""
)

$ErrorActionPreference = "Stop"

if (-not $Hub) {
  $Hub = Split-Path -Parent $PSScriptRoot
}
$Hub = (Resolve-Path -LiteralPath $Hub).Path
$Warteschlange = Join-Path $PSScriptRoot "warteschlange.py"

Write-Host "routine: pflege alles (vorschlagen)"
& python $Warteschlange --hub $Hub einreihen --projekt alles --auftrag "pflege alles" --modus vorschlagen
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
& python $Warteschlange --hub $Hub tick
exit $LASTEXITCODE
