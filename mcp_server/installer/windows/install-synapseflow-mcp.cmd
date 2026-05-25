@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Sta -WindowStyle Hidden -File "%SCRIPT_DIR%install-synapseflow-mcp.ps1" %*
exit /b %errorlevel%
