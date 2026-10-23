import math
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_perm
from app.core.permissions import Perm
from app.core.timeutil import now, to_naive_local
from app.db.session import engine, get_db
from app.models import DataRecord, MetricThreshold, RealtimeData, SystemLog, User
from app.schemas.admin import DatabaseStatus, PoolStatus, SystemLogOut
from app.schemas.common import Page

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/logs", response_model=Page[SystemLogOut], summary="[Admin] 系統日誌查詢")
async def list_logs(
    level: list[str] | None = Query(None, description="INFO / WARNING / ERROR"),
    category: list[str] | None = Query(None, description="request / auth / data / admin / alert / event"),
    username: str | None = None,
    keyword: str | None = Query(None, max_length=100),
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    _: User = Depends(require_perm(Perm.LOG_READ)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SystemLog)
    if level:
        stmt = stmt.where(SystemLog.level.in_([lv.upper() for lv in level]))
    if category:
        stmt = stmt.where(SystemLog.category.in_(category))
    if username:
        stmt = stmt.where(SystemLog.username == username)
    if keyword:
        stmt = stmt.where(SystemLog.message.ilike(f"%{keyword}%") | SystemLog.path.ilike(f"%{keyword}%"))
    if start:
        stmt = stmt.where(SystemLog.created_at >= to_naive_local(start))
    if end:
        stmt = stmt.where(SystemLog.created_at <= to_naive_local(end))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = (
        await db.scalars(stmt.order_by(SystemLog.id.desc()).offset((page - 1) * size).limit(size))
    ).all()
    return Page(items=items, total=total, page=page, size=size, pages=math.ceil(total / size) if total else 0)


@router.get("/db-status", response_model=DatabaseStatus, summary="[Admin] 資料庫狀態監控")
async def db_status(_: User = Depends(require_perm(Perm.SYSTEM_STATUS)), db: AsyncSession = Depends(get_db)):
    pool = engine.pool
    pool_info = PoolStatus(
        pool_class=type(pool).__name__,
        size=getattr(pool, "size", lambda: None)(),
        checked_in=getattr(pool, "checkedin", lambda: None)(),
        checked_out=getattr(pool, "checkedout", lambda: None)(),
        overflow=getattr(pool, "overflow", lambda: None)(),
        status=pool.status(),
    )
    connected, version, latency = True, None, None
    counts: dict[str, int] = {}
    try:
        t0 = time.perf_counter()
        fn = func.sqlite_version() if engine.dialect.name == "sqlite" else func.version()
        version = await db.scalar(select(fn))
        latency = round((time.perf_counter() - t0) * 1000, 2)
        for model in (User, DataRecord, RealtimeData, MetricThreshold, SystemLog):
            counts[model.__tablename__] = await db.scalar(select(func.count()).select_from(model)) or 0
    except Exception:  # noqa: BLE001
        connected = False
    return DatabaseStatus(
        connected=connected,
        dialect=engine.dialect.name,
        server_version=version,
        latency_ms=latency,
        pool=pool_info,
        table_counts=counts,
        checked_at=now(),
    )
