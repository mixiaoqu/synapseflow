# 开发环境启动脚本

Write-Host "🚀 启动SynapseFlow开发环境..." -ForegroundColor Cyan

# 启动数据库
Write-Host ""
Write-Host "启动PostgreSQL数据库..." -ForegroundColor Yellow
docker-compose up -d postgres

Start-Sleep -Seconds 3

# 启动后端
Write-Host ""
Write-Host "启动后端服务..." -ForegroundColor Yellow
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd backend; uv run uvicorn app.main:app --reload"

Start-Sleep -Seconds 2

# 启动前端
Write-Host ""
Write-Host "启动前端服务..." -ForegroundColor Yellow
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd frontend; pnpm dev"

Write-Host ""
Write-Host "✅ 开发环境启动完成！" -ForegroundColor Green
Write-Host ""
Write-Host "服务地址：" -ForegroundColor Cyan
Write-Host "  前端: http://localhost:3000"
Write-Host "  后端: http://localhost:8000"
Write-Host "  API文档: http://localhost:8000/api/v1/docs"
