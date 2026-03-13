"""通用Schema定义"""
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """错误响应模型"""
    success: bool = False
    error: str
    detail: Optional[str] = None


class TimestampMixin(BaseModel):
    """时间戳Mixin"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
