from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import UnauthorizedError, get_current_user
from app.core.exceptions import ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import Message
from app.schemas.user import Token, UserCreate, UserOut
from app.services.audit import log_in_background

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="使用者註冊")
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """註冊新帳號，預設角色為 `user`（Admin 可於系統管理調整）。"""
    dup = await db.scalar(
        select(User).where(or_(User.username == payload.username, User.email == payload.email))
    )
    if dup:
        raise ConflictError("Username or email already registered")
    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=UserRole.USER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    log_in_background(f"User registered: {user.username}", category="auth", username=user.username)
    return user


@router.post("/login", response_model=Token, summary="登入取得 JWT")
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 Password Flow（form-data: `username`, `password`），Swagger 右上角 Authorize 可直接使用。"""
    user = await db.scalar(select(User).where(User.username == form.username))
    ip = request.client.host if request.client else None
    if not user or not verify_password(form.password, user.hashed_password):
        log_in_background(
            f"Login failed: {form.username}", level="WARNING", category="auth", username=form.username, client_ip=ip
        )
        raise UnauthorizedError("Incorrect username or password")
    if not user.is_active:
        raise UnauthorizedError("User is inactive")
    token = create_access_token(user.id, {"role": user.role.value, "username": user.username})
    log_in_background(f"Login success: {user.username}", category="auth", username=user.username, client_ip=ip)
    return Token(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", response_model=Message, summary="登出（記錄事件，Token 由前端丟棄）")
async def logout(user: User = Depends(get_current_user)):
    log_in_background(f"Logout: {user.username}", category="auth", username=user.username)
    return Message(message="Logged out")


@router.get("/me", response_model=UserOut, summary="目前登入者資訊")
async def me(user: User = Depends(get_current_user)):
    return user
