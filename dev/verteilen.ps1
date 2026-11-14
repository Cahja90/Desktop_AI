#legt AGENTS.md in projekte aus liste.yaml, ohne vorhandene zu ueberschreiben
param(
  [string]$Hub = ""
)

$ErrorActionPreference = "Stop"

if (-not $Hub) {
  $Hub = Split-Path -Parent $PSScriptRoot
}
$Hub = (Resolve-Path -LiteralPath $Hub).Path
$Liste = Join-Path $Hub "projekte\liste.yaml"
$ListeLokal = Join-Path $Hub "projekte\liste.lokal.yaml"
if (Test-Path $ListeLokal) { $Liste = $ListeLokal }
$Vorlage = Join-Path $PSScriptRoot "vorlage\AGENTS.md"

if (-not (Test-Path -LiteralPath $Liste)) {
  throw "liste fehlt: $Liste"
}
if (-not (Test-Path -LiteralPath $Vorlage)) {
  throw "vorlage fehlt: $Vorlage"
}

$vorlageText = Get-Content -LiteralPath $Vorlage -Raw -Encoding UTF8
$namen = @()
Get-Content -LiteralPath $Liste -Encoding UTF8 | ForEach-Object {
  if ($_ -match '^\s*-\s*name:\s*(.+)\s*$') {
    $namen += $Matches[1].Trim().Trim('"').Trim("'")
  }
}

function abschnitt_titel([string]$Text) {
  $titels = @()
  foreach ($zeile in ($Text -split "`r?`n")) {
    if ($zeile -match '^#{1,3}\s+(.+)$') {
      $titels += $Matches[1].Trim().ToLowerInvariant()
    }
  }
  return $titels
}

$vorlageAbschnitte = abschnitt_titel $vorlageText
$bericht = @()

foreach ($name in $namen) {
  $ordner = Join-Path $Hub $name
  if (-not (Test-Path -LiteralPath $ordner -PathType Container)) {
    $bericht += "fehlt-ordner: $name"
    continue
  }
  $ziel = Join-Path $ordner "AGENTS.md"
  $devDir = Join-Path $ordner ".dev"
  New-Item -ItemType Directory -Force -Path $devDir | Out-Null

  if (-not (Test-Path -LiteralPath $ziel)) {
    [System.IO.File]::WriteAllText($ziel, $vorlageText, [System.Text.UTF8Encoding]::new($false))
    $bericht += "neu: $name"
    continue
  }

  $vorhanden = Get-Content -LiteralPath $ziel -Raw -Encoding UTF8
  $haben = abschnitt_titel $vorhanden
  $fehlend = @()
  foreach ($abs in $vorlageAbschnitte) {
    if ($haben -notcontains $abs) {
      $fehlend += $abs
    }
  }
  if ($fehlend.Count -eq 0) {
    $bericht += "ok: $name"
    continue
  }

  $vorschlag = Join-Path $devDir "agents-vorschlag.md"
  $text = @"
# agents-vorschlag

vorhandene AGENTS.md wurde nicht ueberschrieben.
fehlende abschnitte aus der hub-vorlage:

$($fehlend | ForEach-Object { "- $_" } | Out-String)

---
# vorlage (referenz)

$vorlageText
"@
  [System.IO.File]::WriteAllText($vorschlag, $text, [System.Text.UTF8Encoding]::new($false))
  $bericht += "vorschlag: $name ($($fehlend -join ', '))"
}

$bericht | ForEach-Object { Write-Host $_ }
Write-Host "fertig · $($namen.Count) projekte in liste"
