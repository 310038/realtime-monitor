import math

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_perm
from app.core.exceptions import BadRequestError, NotFoundError, PermissionDeniedError
from app.core.permissions import Perm, has_perm
from app.core.timeutil import now, to_naive_local
from app.db.session import get_db
from app.models.record import DataRecord
from app.models.user import User
from app.schemas.common import Page
from app.schemas.record import ImportResult, RecordCreate, RecordOut, RecordUpdate, SortField, SortOrder
from app.services import thresholds
from app.services.audit import log_in_background
from app.services.importer import parse_csv, parse_json
from app.services.record_filters import RecordFilters, record_filters

router = APIRouter(prefix="/records", tags=["Records"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
IMPORT_CHUNK = 500


async def _get_or_404(db: AsyncSession, record_id: int) -> DataRecord:
    rec = await db.scalar(
        select(DataRecord).where(DataRecord.id == record_id).execution_options(populate_existing=True)
    )
    if not rec:
        raise NotFoundError("Record")
    return rec


def _ensure_can_modify(user: User, rec: DataRecord, own: Perm, any_: Perm) -> None:
    if has_perm(user.role, any_):
        return
    if has_perm(user.role, own) and rec.owner_id == user.id:
        return
    raise PermissionDeniedError("Only the creator or an admin can modify this record")


@router.get("", response_model=Page[RecordOut], summary="查詢資料（分頁 / 篩選 / 排序）")
async def list_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    sort_by: SortField = Query(SortField.timestamp),
    order: SortOrder = Query(SortOrder.desc),
    filters: RecordFilters = Depends(record_filters),
    _: User = Depends(require_perm(Perm.RECORD_READ)),
    db: AsyncSession = Depends(get_db),
):
    stmt = filters.apply(select(DataRecord))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = getattr(DataRecord, sort_by.value)
    stmt = stmt.order_by(col.asc() if order == SortOrder.asc else col.desc(), DataRecord.id.desc())
    items = (await db.scalars(stmt.offset((page - 1) * size).limit(size))).unique().all()
    return Page(items=items, total=total, page=page, size=size, pages=math.ceil(total / size) if total else 0)


@router.get("/categories", response_model=list[str], summary="所有分類")
async def list_categories(_: User = Depends(require_perm(Perm.RECORD_READ)), db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(DataRecord.category).distinct().order_by(DataRecord.category))).all()


@router.post("", response_model=RecordOut, status_code=status.HTTP_201_CREATED, summary="新增資料")
async def create_record(
    payload: RecordCreate,
    user: User = Depends(require_perm(Perm.RECORD_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump()
    data["timestamp"] = to_naive_local(data["timestamp"]) or now()
    rec = DataRecord(**data, owner_id=user.id, is_anomaly=thresholds.is_anomaly(payload.category, payload.value))
    db.add(rec)
    await db.commit()
    log_in_background(f"Record #{rec.id} created", category="data", username=user.username)
    return await _get_or_404(db, rec.id)


@router.post("/import", response_model=ImportResult, summary="批量匯入（CSV / JSON）")
async def import_records(
    file: UploadFile = File(..., description="CSV（欄位：title,value,category,timestamp,description）或 JSON 陣列"),
    user: User = Depends(require_perm(Perm.RECORD_IMPORT)),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise BadRequestError("File too large (max 5MB)")
    name = (file.filename or "").lower()
    if name.endswith(".csv") or file.content_type in ("text/csv", "application/vnd.ms-excel"):
        rows, errors = parse_csv(content)
    elif name.endswith(".json") or file.content_type == "application/json":
        rows, errors = parse_json(content)
    else:
        raise BadRequestError("Unsupported file type, use .csv or .json")

    anomalies = 0
    for i in range(0, len(rows), IMPORT_CHUNK):
        objs = []
        for r in rows[i : i + IMPORT_CHUNK]:
            flag = thresholds.is_anomaly(r.category, r.value)
            anomalies += flag
            objs.append(DataRecord(**r.model_dump(), owner_id=user.id, is_anomaly=flag))
        db.add_all(objs)
        await db.flush()
    await db.commit()
    log_in_background(
        f"Imported {len(rows)} records from {file.filename} ({len(errors)} failed)", category="data", username=user.username
    )
    return ImportResult(
        total=len(rows) + len(errors), imported=len(rows), failed=len(errors), anomalies=anomalies, errors=errors[:100]
    )


@router.get("/{record_id}", response_model=RecordOut, summary="取得單筆資料")
async def get_record(record_id: int, _: User = Depends(require_perm(Perm.RECORD_READ)), db: AsyncSession = Depends(get_db)):
    return await _get_or_404(db, record_id)


async def _update(record_id: int, payload: RecordUpdate, user: User, db: AsyncSession) -> DataRecord:
    rec = await _get_or_404(db, record_id)
    _ensure_can_modify(user, rec, Perm.RECORD_UPDATE_OWN, Perm.RECORD_UPDATE_ANY)
    data = payload.model_dump(exclude_unset=True)
    if "timestamp" in data:
        data["timestamp"] = to_naive_local(data["timestamp"]) or rec.timestamp
    for k, v in data.items():
        if v is None and k in ("title", "value", "category"):
            raise BadRequestError(f"'{k}' cannot be null")
        setattr(rec, k, v)
    rec.is_anomaly = thresholds.is_anomaly(rec.category, rec.value)
    await db.commit()
    log_in_background(f"Record #{rec.id} updated", category="data", username=user.username)
    return await _get_or_404(db, record_id)


@router.put("/{record_id}", response_model=RecordOut, summary="更新資料（僅限創建者或 Admin）")
async def put_record(
    record_id: int, payload: RecordCreate, user: User = Depends(require_perm(Perm.RECORD_READ)), db: AsyncSession = Depends(get_db)
):
    full = RecordUpdate(**payload.model_dump())
    return await _update(record_id, full, user, db)


@router.patch("/{record_id}", response_model=RecordOut, summary="部分更新資料（僅限創建者或 Admin）")
async def patch_record(
    record_id: int, payload: RecordUpdate, user: User = Depends(require_perm(Perm.RECORD_READ)), db: AsyncSession = Depends(get_db)
):
    return await _update(record_id, payload, user, db)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT, summary="刪除資料（僅限創建者或 Admin）")
async def delete_record(record_id: int, user: User = Depends(require_perm(Perm.RECORD_READ)), db: AsyncSession = Depends(get_db)):
    rec = await _get_or_404(db, record_id)
    _ensure_can_modify(user, rec, Perm.RECORD_DELETE_OWN, Perm.RECORD_DELETE_ANY)
    await db.delete(rec)
    await db.commit()
    log_in_background(f"Record #{record_id} deleted", category="data", username=user.username)
