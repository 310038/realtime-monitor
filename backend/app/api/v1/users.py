import math

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_perm
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.permissions import ROLE_PERMISSIONS, Perm
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import Page
from app.schemas.user import UserAdminUpdate, UserOut, UserUpdateMe
from app.services.audit import log_in_background

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut, summary="取得個人資料")
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut, summary="更新個人資料 / 密碼")
async def update_me(payload: UserUpdateMe, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] != user.email:
        if await db.scalar(select(User.id).where(User.email == data["email"])):
            raise ConflictError("Email already in use")
    if pwd := data.pop("password", None):
        user.hashed_password = hash_password(pwd)
    for k, v in data.items():
        setattr(user, k, v)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me/permissions", response_model=list[str], summary="目前角色的權限清單")
async def my_permissions(user: User = Depends(get_current_user)):
    return sorted(p.value for p in ROLE_PERMISSIONS[user.role])


@router.get("", response_model=Page[UserOut], summary="[Admin] 使用者列表")
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    search: str | None = Query(None, description="username / email / 姓名 關鍵字"),
    role: UserRole | None = None,
    is_active: bool | None = None,
    _: User = Depends(require_perm(Perm.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.email.ilike(like), User.full_name.ilike(like)))
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = (await db.scalars(stmt.order_by(User.id).offset((page - 1) * size).limit(size))).all()
    return Page(items=items, total=total, page=page, size=size, pages=math.ceil(total / size) if total else 0)


@router.get("/{user_id}", response_model=UserOut, summary="[Admin] 取得使用者")
async def get_user(user_id: int, _: User = Depends(require_perm(Perm.USER_MANAGE)), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User")
    return user


@router.patch("/{user_id}", response_model=UserOut, summary="[Admin] 調整角色 / 啟用狀態")
async def update_user(
    user_id: int,
    payload: UserAdminUpdate,
    admin: User = Depends(require_perm(Perm.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User")
    data = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and (data.get("role", UserRole.ADMIN) != UserRole.ADMIN or data.get("is_active") is False):
        raise BadRequestError("You cannot demote or deactivate yourself")
    for k, v in data.items():
        setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    log_in_background(
        f"User {user.username} updated by {admin.username}: {payload.model_dump(exclude_unset=True, mode='json')}",
        category="admin",
        username=admin.username,
    )
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="[Admin] 刪除使用者")
async def delete_user(
    user_id: int, admin: User = Depends(require_perm(Perm.USER_MANAGE)), db: AsyncSession = Depends(get_db)
):
    user = await db.get(User, user_id)
    if not user:
        raise NotFoundError("User")
    if user.id == admin.id:
        raise BadRequestError("You cannot delete yourself")
    await db.delete(user)
    await db.commit()
    log_in_background(f"User {user.username} deleted by {admin.username}", category="admin", username=admin.username)
