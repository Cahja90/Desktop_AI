#kurze windows-meldung fuer pr bereit / lauf fehler
param(
  [Parameter(Mandatory = $true)][string]$Titel,
  [Parameter(Mandatory = $true)][string]$Text
)

$ErrorActionPreference = "SilentlyContinue"

try {
  Add-Type -AssemblyName System.Windows.Forms | Out-Null
  Add-Type -AssemblyName System.Drawing | Out-Null
  $icon = New-Object System.Windows.Forms.NotifyIcon
  $icon.Icon = [System.Drawing.SystemIcons]::Information
  $icon.Visible = $true
  $icon.BalloonTipTitle = $Titel
  $icon.BalloonTipText = $Text
  $icon.ShowBalloonTip(4000)
  Start-Sleep -Milliseconds 4500
  $icon.Dispose()
} catch {
  Write-Host "$Titel · $Text"
}
