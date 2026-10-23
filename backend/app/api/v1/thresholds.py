from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_perm
from app.core.exceptions import NotFoundError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.realtime import MetricThreshold
from app.models.user import User
from app.schemas.realtime import ThresholdOut, ThresholdUpsert
from app.services import thresholds as cache
from app.services.audit import log_in_background

router = APIRouter(prefix="/thresholds", tags=["Thresholds"])


@router.get("", response_model=list[ThresholdOut], summary="告警閾值列表")
async def list_thresholds(_: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(MetricThreshold).order_by(MetricThreshold.name))).all()


@router.put("/{name}", response_model=ThresholdOut, summary="[Admin] 新增或更新閾值（指標或資料分類）")
async def upsert_threshold(
    name: str,
    payload: ThresholdUpsert,
    admin: User = Depends(require_perm(Perm.THRESHOLD_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(select(MetricThreshold).where(MetricThreshold.name == name))
    if row:
        row.threshold = payload.threshold
    else:
        row = MetricThreshold(name=name, threshold=payload.threshold)
        db.add(row)
    await db.commit()
    await db.refresh(row)
    cache.set_value(name, payload.threshold)
    log_in_background(f"Threshold {name} set to {payload.threshold}", category="admin", username=admin.username)
    return row


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT, summary="[Admin] 刪除閾值（回到預設值）")
async def delete_threshold(
    name: str, admin: User = Depends(require_perm(Perm.THRESHOLD_MANAGE)), db: AsyncSession = Depends(get_db)
):
    row = await db.scalar(select(MetricThreshold).where(MetricThreshold.name == name))
    if not row:
        raise NotFoundError("Threshold")
    await db.delete(row)
    await db.commit()
    cache.remove(name)
    log_in_background(f"Threshold {name} deleted", category="admin", username=admin.username)
