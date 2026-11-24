[CmdletBinding()]
param(
  [switch]$SkipTests,
  [switch]$DryRun,
  [switch]$NoAgentIntegration
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }
$home_ = Join-Path $env:LOCALAPPDATA 'GTAForge'
$binDir = Join-Path $home_ 'bin'
$launcher = Join-Path $binDir 'gtaforge.cmd'
$skillSrc = Join-Path $root 'skills\gta-forge'
$skillTargets = @(
  (Join-Path $env:USERPROFILE '.claude\skills'),
  (Join-Path $env:USERPROFILE '.agents\skills')
) | Where-Object { Test-Path $_ }

Write-Host '== GTA Forge install =='
Write-Host "root: $root"
if ($DryRun) {
  Write-Host 'Dry run: nothing will be changed.'
  Write-Host "  venv:     $root\.venv (pip install -e this folder)"
  Write-Host "  launcher: $launcher (added to the user PATH)"
  if (-not $NoAgentIntegration) { foreach ($t in $skillTargets) { Write-Host "  agent skill: $t\gta-forge" } }
  return
}

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw 'python not found on PATH (3.10+)' }
& $py.Source -m venv (Join-Path $root '.venv')
$venvPy = Join-Path $root '.venv\Scripts\python.exe'
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -e $root
if (-not $SkipTests) {
  & $venvPy (Join-Path $root 'tests\run_tests.py')
  if ($LASTEXITCODE -ne 0) { throw 'tests failed' }
}
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
$launcherText = @"
@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "GTA_FORGE_ROOT=$root"
if exist "%GTA_FORGE_ROOT%\.venv\Scripts\python.exe" (
  "%GTA_FORGE_ROOT%\.venv\Scripts\python.exe" -m gtaforge %*
  exit /b %ERRORLEVEL%
)
set "PYTHONPATH=%GTA_FORGE_ROOT%src;%PYTHONPATH%"
python -m gtaforge %*
exit /b %ERRORLEVEL%
"@
[IO.File]::WriteAllText($launcher, $launcherText.Replace("`n", "`r`n"), [Text.Encoding]::ASCII)
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -notlike "*$binDir*") {
  [Environment]::SetEnvironmentVariable('Path', ($userPath.TrimEnd(';') + ';' + $binDir), 'User')
  Write-Host "added $binDir to the user PATH (restart the shell)"
}
if (-not $NoAgentIntegration) {
  foreach ($t in $skillTargets) {
    $dst = Join-Path $t 'gta-forge'
    if (Test-Path $dst) { Copy-Item -Recurse -Force (Join-Path $dst '*') (Join-Path $env:TEMP 'gtaforge-skill-backup') -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force -Path $t | Out-Null
    Copy-Item -Recurse -Force $skillSrc $dst
    Write-Host "skill installed: $dst"
  }
}
Write-Host 'done. Open a new shell, then: gtaforge doctor'