@echo off
setlocal
where node >nul 2>nul
if errorlevel 1 (
  echo [LangChain RAG 知识库 MCP] Node.js is not installed.
  echo [LangChain RAG 知识库 MCP] Install Node.js 20+ and try again.
  exit /b 1
)

node "%~dp0app\dist\index.js"
exit /b %errorlevel%
