"""FastAPI 依賴：取得目前使用者、權限檢查。"""
from collections.abc import Callable

import jwt
from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, PermissionDeniedError
from app.core.permissions import Perm, has_perm
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Could not validate credentials"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", message)


async def get_user_from_token(token: str, db: AsyncSession) -> User:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise UnauthorizedError()
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await get_user_from_token(token, db)
    request.state.username = user.username  # 給存取日誌中介層使用
    return user


def require_perm(*perms: Perm) -> Callable:
    async def checker(user: User = Depends(get_current_user)) -> User:
        missing = [p.value for p in perms if not has_perm(user.role, p)]
        if missing:
            raise PermissionDeniedError(f"Role '{user.role.value}' lacks permission: {', '.join(missing)}")
        return user

    return checker
