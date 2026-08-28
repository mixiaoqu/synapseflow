"""通用Schema定义"""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


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
