[CmdletBinding()]
param([switch]$RemoveCache, [switch]$KeepSkill)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$home_ = Join-Path $env:LOCALAPPDATA 'GTAForge'
$binDir = Join-Path $home_ 'bin'
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath) {
  $parts = $userPath -split ';' | Where-Object { $_ -and ($_ -ne $binDir) }
  [Environment]::SetEnvironmentVariable('Path', ($parts -join ';'), 'User')
}
if (Test-Path $binDir) { Remove-Item -Recurse -Force $binDir }
Write-Host 'launcher and PATH entry removed'
if (-not $KeepSkill) {
  foreach ($t in @((Join-Path $env:USERPROFILE '.claude\skills\gta-forge'), (Join-Path $env:USERPROFILE '.agents\skills\gta-forge'))) {
    if (Test-Path $t) { Remove-Item -Recurse -Force $t; Write-Host "skill removed: $t" }
  }
}
if ($RemoveCache -and (Test-Path $home_)) { Remove-Item -Recurse -Force $home_ }
Write-Host 'uninstall done (source folder untouched)'