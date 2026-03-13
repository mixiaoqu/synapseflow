# SynapseFlow初始化脚本（Windows PowerShell）

Write-Host "🚀 SynapseFlow 初始化脚本" -ForegroundColor Cyan
Write-Host ""

# 检查Python
Write-Host "检查Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Python已安装: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "❌ 未找到Python，请先安装Python 3.11+" -ForegroundColor Red
    exit 1
}

# 检查Node.js
Write-Host "检查Node.js..." -ForegroundColor Yellow
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Node.js已安装: $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "❌ 未找到Node.js，请先安装Node.js 20+" -ForegroundColor Red
    exit 1
}

# 检查Docker
Write-Host "检查Docker..." -ForegroundColor Yellow
$dockerVersion = docker --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Docker已安装: $dockerVersion" -ForegroundColor Green
} else {
    Write-Host "⚠️  未找到Docker，Docker功能将不可用" -ForegroundColor Yellow
}

# 安装uv
Write-Host ""
Write-Host "安装uv包管理器..." -ForegroundColor Yellow
$uvCheck = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCheck) {
    Write-Host "✅ uv已安装" -ForegroundColor Green
} else {
    Write-Host "正在安装uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    Write-Host "✅ uv安装完成" -ForegroundColor Green
}

# 配置环境变量
Write-Host ""
Write-Host "配置环境变量..." -ForegroundColor Yellow
if (!(Test-Path "backend\.env")) {
    Copy-Item "backend\.env.example" "backend\.env"
    Write-Host "✅ 已创建 backend\.env，请编辑填入API密钥" -ForegroundColor Green
} else {
    Write-Host "⚠️  backend\.env已存在，跳过" -ForegroundColor Yellow
}

if (!(Test-Path "frontend\.env.local")) {
    Copy-Item "frontend\.env.local.example" "frontend\.env.local"
    Write-Host "✅ 已创建 frontend\.env.local" -ForegroundColor Green
} else {
    Write-Host "⚠️  frontend\.env.local已存在，跳过" -ForegroundColor Yellow
}

# 安装后端依赖
Write-Host ""
Write-Host "安装后端依赖..." -ForegroundColor Yellow
Set-Location backend
uv sync
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 后端依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "❌ 后端依赖安装失败" -ForegroundColor Red
}
Set-Location ..

# 安装前端依赖
Write-Host ""
Write-Host "安装前端依赖..." -ForegroundColor Yellow
Set-Location frontend
pnpm install
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 前端依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "❌ 前端依赖安装失败" -ForegroundColor Red
}
Set-Location ..

# 完成
Write-Host ""
Write-Host "🎉 初始化完成！" -ForegroundColor Green
Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "1. 编辑 backend\.env 填入API密钥"
Write-Host "2. 启动数据库：docker-compose up -d postgres"
Write-Host "3. 启动后端：cd backend && uv run uvicorn app.main:app --reload"
Write-Host "4. 启动前端：cd frontend && pnpm dev"
Write-Host ""
Write-Host "或使用Docker一键启动：docker-compose up -d"
