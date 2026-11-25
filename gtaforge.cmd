@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Run GTA Forge from this folder without installing it.
rem No parenthesized block around the python call: %ERRORLEVEL% inside one is expanded before python runs.
set "GTA_FORGE_ROOT=%~dp0"
if not exist "%GTA_FORGE_ROOT%.venv\Scripts\python.exe" goto system_python
"%GTA_FORGE_ROOT%.venv\Scripts\python.exe" -m gtaforge %*
exit /b %ERRORLEVEL%
:system_python
set "PYTHONPATH=%GTA_FORGE_ROOT%src;%PYTHONPATH%"
python -m gtaforge %*
exit /b %ERRORLEVEL%
