@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Run GTA Forge from this folder without installing it.
set "GTA_FORGE_ROOT=%~dp0"
if exist "%GTA_FORGE_ROOT%.venv\Scripts\python.exe" (
  "%GTA_FORGE_ROOT%.venv\Scripts\python.exe" -m gtaforge %*
  exit /b %ERRORLEVEL%
)
set "PYTHONPATH=%GTA_FORGE_ROOT%src;%PYTHONPATH%"
python -m gtaforge %*
exit /b %ERRORLEVEL%