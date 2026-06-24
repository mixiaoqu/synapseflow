"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.config.settings import settings
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.db.session import get_db
from app.models.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from app.repositories.user_repository import UserRepository

router = APIRouter()


def auth_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
        },
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    body: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    if not settings.ENABLE_PUBLIC_REGISTRATION:
        raise auth_error(403, "PUBLIC_REGISTRATION_DISABLED", "当前暂未开放公开注册。")

    repo = UserRepository(db)
    if await repo.get_by_username(body.username):
        raise auth_error(409, "USERNAME_ALREADY_EXISTS", "用户名已存在，请更换后重试。")
    if await repo.get_by_email(body.email):
        raise auth_error(409, "EMAIL_ALREADY_EXISTS", "邮箱已存在，请更换后重试。")
    return await repo.create_user(
        username=body.username,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    user = await repo.get_by_identity(body.username_or_email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise auth_error(401, "INVALID_CREDENTIALS", "账号或密码不正确，请重新输入。")
    if not user.is_active:
        raise auth_error(403, "USER_INACTIVE", "账号已停用，请联系管理员。")

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token, user=user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
