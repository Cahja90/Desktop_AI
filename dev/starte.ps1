#startet einen cursor-cli agenten im projektordner
param(
  [Parameter(Mandatory = $true)][string]$Projekt,
  [Parameter(Mandatory = $true)][string]$Auftrag,
  [ValidateSet("vorschlagen", "selber")][string]$Modus = "vorschlagen",
  [string]$Hub = "",
  [switch]$Warten
)

$ErrorActionPreference = "Stop"

if (-not $Hub) {
  $Hub = Split-Path -Parent $PSScriptRoot
}
$Hub = (Resolve-Path -LiteralPath $Hub).Path
$Projekt = $Projekt.Trim()
if ($Projekt -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$') {
  throw "ungueltiger projektname: $Projekt"
}

$ProjektPfad = Join-Path $Hub $Projekt
if (-not (Test-Path -LiteralPath $ProjektPfad -PathType Container)) {
  throw "projektordner fehlt: $ProjektPfad"
}

$DevDir = Join-Path $ProjektPfad ".dev"
$LaeufeDir = Join-Path $DevDir "laeufe"
New-Item -ItemType Directory -Force -Path $LaeufeDir | Out-Null

$Zeit = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPfad = Join-Path $LaeufeDir "$Zeit.log"
$ProtokollPfad = Join-Path $DevDir "protokoll.md"
$StatusPfad = Join-Path $PSScriptRoot "status.json"
$StatusLokal = Join-Path $PSScriptRoot "status.lokal.json"
if (Test-Path $StatusLokal) { $StatusPfad = $StatusLokal }
$ToastSkript = Join-Path $PSScriptRoot "toast.ps1"
$UebersichtPfad = Join-Path $Hub ".dev\uebersicht.md"

$RahmenZeilen = @(
  "du bist der pflege-agent fuer dieses repo.",
  "modus: $Modus",
  "halte dich an AGENTS.md hier.",
  "schreib am ende .dev\protokoll.md (datum, uhrzeit, angeschaut, gefunden, gemacht, offen, links).",
  "auftrag: $Auftrag"
)
if ($Modus -eq "vorschlagen") {
  $RahmenZeilen += "wichtig: nur lesen und vorschlagen. nichts aendern. report max 10 zeilen, 2-3 wege mit aufwand."
}
if ($Modus -eq "selber") {
  $RahmenZeilen += "wichtig: nur in diesem ordner arbeiten. lokal bleiben. nicht git pushen, keinen pull request oeffnen, kein merge, kein deploy. committen macht die zentrale, nicht du."
}
$Rahmen = ($RahmenZeilen -join " ")

function lies_json([string]$Pfad, $Fallback) {
  if (-not (Test-Path -LiteralPath $Pfad)) {
    return $Fallback
  }
  $roh = Get-Content -LiteralPath $Pfad -Raw -Encoding UTF8
  if (-not $roh) {
    return $Fallback
  }
  return ($roh | ConvertFrom-Json)
}

function speicher_json($Objekt, [string]$Pfad) {
  $dir = Split-Path -Parent $Pfad
  if ($dir -and -not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
  $text = $Objekt | ConvertTo-Json -Depth 8
  [System.IO.File]::WriteAllText($Pfad, $text, [System.Text.UTF8Encoding]::new($false))
}

function setze_status([hashtable]$Felder) {
  $status = lies_json $StatusPfad ([pscustomobject]@{ tag = ""; laeufe_heute = 0; projekte = [pscustomobject]@{} })
  if (-not $status.projekte) {
    $status | Add-Member -NotePropertyName projekte -NotePropertyValue ([pscustomobject]@{}) -Force
  }
  $eintrag = [ordered]@{
    name            = $Projekt
    pfad            = $ProjektPfad
    zustand         = "laeuft"
    modus           = $Modus
    pid             = $null
    start           = ""
    ende            = ""
    letzter_auftrag = $Auftrag
    log_pfad        = $LogPfad
    protokoll_pfad  = $ProtokollPfad
    pr_link         = ""
    exitcode        = $null
  }
  $alt = $status.projekte.$Projekt
  if ($alt) {
    foreach ($key in $eintrag.Keys) {
      if ($null -ne $alt.$key -and $key -notin @("zustand", "modus", "letzter_auftrag", "log_pfad", "protokoll_pfad")) {
        #behalte nur was unten gesetzt wird
      }
    }
    if ($alt.pr_link) { $eintrag.pr_link = [string]$alt.pr_link }
  }
  foreach ($key in $Felder.Keys) {
    $eintrag[$key] = $Felder[$key]
  }
  $map = @{}
  if ($status.projekte.PSObject.Properties) {
    foreach ($prop in $status.projekte.PSObject.Properties) {
      $map[$prop.Name] = $prop.Value
    }
  }
  $map[$Projekt] = [pscustomobject]$eintrag
  $status.projekte = [pscustomobject]$map
  speicher_json $status $StatusPfad
}

function aktualisiere_uebersicht {
  $status = lies_json $StatusPfad ([pscustomobject]@{ projekte = [pscustomobject]@{} })
  $zeilen = @("# uebersicht", "", "stand: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')", "")
  if ($status.projekte) {
    foreach ($prop in $status.projekte.PSObject.Properties) {
      $p = $prop.Value
      $zeilen += "- $($p.name): $($p.zustand) · $($p.modus) · $($p.letzter_auftrag)"
      if ($p.pr_link) { $zeilen += "  pr: $($p.pr_link)" }
      if ($p.log_pfad) { $zeilen += "  log: $($p.log_pfad)" }
    }
  }
  $dir = Split-Path -Parent $UebersichtPfad
  if (-not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
  [System.IO.File]::WriteAllText($UebersichtPfad, ($zeilen -join "`n") + "`n", [System.Text.UTF8Encoding]::new($false))
}

$agentExe = $null
$agentCmdPath = Join-Path $env:LOCALAPPDATA "cursor-agent\agent.cmd"
if (Test-Path -LiteralPath $agentCmdPath) {
  $agentExe = $agentCmdPath
} else {
  $agentCmd = Get-Command agent.cmd -ErrorAction SilentlyContinue
  if (-not $agentCmd) { $agentCmd = Get-Command agent -ErrorAction SilentlyContinue }
  if (-not $agentCmd) {
    throw "agent nicht im pfad. erst 'agent login' oder CURSOR_API_KEY setzen."
  }
  $agentExe = $agentCmd.Source
}

#prompt in datei (lesbar) und als eine zeile an agent
$PromptPfad = Join-Path $DevDir "letzter-prompt.txt"
[System.IO.File]::WriteAllText($PromptPfad, ($RahmenZeilen -join "`n") + "`n", [System.Text.UTF8Encoding]::new($false))
$PromptKurz = "lies .dev/letzter-prompt.txt und fuehre genau diesen auftrag aus. $Rahmen"

#key nie in dateien schreiben; nur env nutzen falls gesetzt
function baue_args([string]$Format) {
  $liste = @(
    "-p",
    "--force",
    "--trust",
    "--workspace", $ProjektPfad,
    "--output-format", $Format
  )
  if ($Modus -eq "vorschlagen") {
    $liste += @("--mode", "plan")
  }
  $liste += $PromptKurz
  return $liste
}

function quote_args([string[]]$ArgsIn) {
  $escaped = @()
  foreach ($a in $ArgsIn) {
    if ($null -eq $a) { continue }
    if ($a -match '[\s"]') {
      $escaped += '"' + ($a -replace '\\', '\\' -replace '"', '\"') + '"'
    } else {
      $escaped += $a
    }
  }
  return ($escaped -join " ")
}

$Start = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
setze_status @{
  zustand = "laeuft"
  modus   = $Modus
  start   = $Start
  ende    = ""
  pid     = $null
  letzter_auftrag = $Auftrag
  log_pfad = $LogPfad
  protokoll_pfad = $ProtokollPfad
}
aktualisiere_uebersicht

Push-Location -LiteralPath $ProjektPfad
try {
  $formate = @("stream-json", "text")
  $exitCode = 1
  $usedPid = $null
  $lastOut = ""
  $lastErr = ""
  foreach ($format in $formate) {
    $agentArgs = baue_args $format
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $agentExe
    $psi.Arguments = quote_args $agentArgs
    $psi.WorkingDirectory = $ProjektPfad
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $null = $proc.Start()
    $usedPid = $proc.Id
    setze_status @{
      zustand = "laeuft"
      pid     = $proc.Id
      start   = $Start
    }
    aktualisiere_uebersicht

    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()
    $proc.WaitForExit()
    $lastOut = $stdoutTask.Result
    $lastErr = $stderrTask.Result
    $exitCode = $proc.ExitCode

    $logText = "=== format $format ===`n=== stdout ===`n$lastOut`n=== stderr ===`n$lastErr`n=== exit $exitCode ===`n"
    [System.IO.File]::WriteAllText($LogPfad, $logText, [System.Text.UTF8Encoding]::new($false))

    if ($exitCode -eq 0) {
      break
    }
    #bei stream-json fehlern einmal text versuchen
    if ($format -eq "stream-json" -and ($lastErr + $lastOut) -match "stream-json|output-format|invalid") {
      continue
    }
    break
  }

  $Ende = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
  $Zustand = if ($exitCode -eq 0) { "fertig" } else { "fehler" }

  #pr-link aus protokoll ziehen falls vorhanden
  $prLink = ""
  if (Test-Path -LiteralPath $ProtokollPfad) {
    $prot = Get-Content -LiteralPath $ProtokollPfad -Raw -Encoding UTF8
    $m = [regex]::Match($prot, 'https://github\.com/[^\s]+/pull/\d+')
    if ($m.Success) {
      $prLink = $m.Value
      $Zustand = "pr-offen"
    }
  }

  setze_status @{
    zustand  = $Zustand
    pid      = $null
    start    = $Start
    ende     = $Ende
    exitcode = $exitCode
    pr_link  = $prLink
  }
  aktualisiere_uebersicht

  if (Test-Path -LiteralPath $ToastSkript) {
    $titel = if ($Zustand -eq "fehler") { "dev lauf fehler" } elseif ($Zustand -eq "pr-offen") { "dev pr bereit" } else { "dev lauf fertig" }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $ToastSkript -Titel $titel -Text "$Projekt · $Zustand" | Out-Null
  }

  Write-Host "projekt=$Projekt zustand=$Zustand pid_war=$usedPid log=$LogPfad"
  exit $exitCode
} catch {
  $Ende = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
  setze_status @{
    zustand = "fehler"
    ende    = $Ende
    pid     = $null
  }
  aktualisiere_uebersicht
  throw
} finally {
  Pop-Location
}
