@echo off
setlocal
where node >nul 2>nul
if errorlevel 1 (
  echo [SynapseFlow MCP] Node.js is not installed.
  echo [SynapseFlow MCP] Install Node.js 20+ and try again.
  exit /b 1
)

node "%~dp0app\dist\index.js"
exit /b %errorlevel%
