"""FastAPI应用主入口"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import config_registry, settings
from app.core.logging_config import setup_logging

app_config = config_registry.get_app_config()



@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging()
    from loguru import logger
    logger.info("{} v{} 启动中", app_config.project_name, app_config.version)

    if settings.LANGSMITH_TRACING and settings.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        if settings.LANGSMITH_PROJECT:
            os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
        if settings.LANGSMITH_WORKSPACE_ID:
            os.environ["LANGSMITH_WORKSPACE_ID"] = settings.LANGSMITH_WORKSPACE_ID
        logger.info("LangSmith 追踪已启用")

    # 后台预热 docling 模型下载，不阻塞服务启动
    asyncio.create_task(_warmup_docling_models())

    logger.info("应用就绪，预览目录: {}", settings.PREVIEW_DIR)
    yield

    logger.info("应用关闭")


app = FastAPI(
    title=app_config.project_name,
    description=app_config.description,
    version=app_config.version,
    openapi_url=f"{app_config.api_v1_str}/openapi.json",
    docs_url=f"{app_config.api_v1_str}/docs",
    redoc_url=f"{app_config.api_v1_str}/redoc",
    lifespan=lifespan
)

# CORS配置（支持SSE）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # 允许前端访问所有响应头
)

# 挂载静态文件目录（用于预览）
# 确保目录存在后再挂载
os.makedirs(settings.PREVIEW_DIR, exist_ok=True)
app.mount("/preview", StaticFiles(directory=settings.PREVIEW_DIR), name="preview")

# 注册API路由
app.include_router(api_router, prefix=app_config.api_v1_str)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": f"Welcome to {app_config.project_name}",
        "version": app_config.version,
        "docs": f"{app_config.api_v1_str}/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": app_config.project_name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
