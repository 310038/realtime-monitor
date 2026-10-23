import asyncio
import json
import math
from datetime import datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_user_from_token, require_perm
from app.core.exceptions import AppException
from app.core.permissions import Perm, has_perm
from app.core.timeutil import to_naive_local
from app.db.session import AsyncSessionLocal, get_db
from app.models.realtime import RealtimeData
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.realtime import GeneratorStatus, RealtimeOut
from app.services.audit import log_in_background
from app.services.batch_writer import batch_writer
from app.services.generator import generator
from app.services.ws_manager import Client, manager

router = APIRouter(prefix="/realtime", tags=["Realtime"])


def _status() -> GeneratorStatus:
    return GeneratorStatus(
        running=generator.running,
        metrics=settings.REALTIME_METRICS,
        interval_seconds=settings.GENERATOR_INTERVAL_SECONDS,
        buffer_size=batch_writer.size,
        batch_max_size=settings.BATCH_MAX_SIZE,
        flush_interval_seconds=settings.BATCH_FLUSH_INTERVAL_SECONDS,
        total_generated=generator.total_generated,
        total_flushed=batch_writer.total_flushed,
        last_flush_at=batch_writer.last_flush_at,
        last_flush_reason=batch_writer.last_flush_reason,
        websocket_clients=manager.count,
    )


@router.get("/status", response_model=GeneratorStatus, summary="產生器 / 批次寫入器狀態")
async def realtime_status(_: User = Depends(require_perm(Perm.REALTIME_READ))):
    return _status()


@router.get("/latest", summary="記憶體中最近的即時資料（圖表初始化用）")
async def latest(
    limit: int = Query(300, ge=1, le=2400),
    _: User = Depends(require_perm(Perm.REALTIME_READ)),
):
    return generator.snapshot(limit)


@router.post("/generator/start", response_model=GeneratorStatus, summary="[Admin] 啟動產生器")
async def start_generator(admin: User = Depends(require_perm(Perm.REALTIME_CONTROL))):
    if generator.start():
        log_in_background("Generator started", category="admin", username=admin.username)
    return _status()


@router.post("/generator/stop", response_model=GeneratorStatus, summary="[Admin] 停止產生器")
async def stop_generator(admin: User = Depends(require_perm(Perm.REALTIME_CONTROL))):
    if await generator.stop():
        await batch_writer.flush("generator-stop")
        log_in_background("Generator stopped", category="admin", username=admin.username)
    return _status()


@router.post("/flush", response_model=Message, summary="[Admin] 立即將緩衝區批次寫入 DB")
async def flush(_: User = Depends(require_perm(Perm.REALTIME_CONTROL))):
    n = await batch_writer.flush("manual")
    return Message(message=f"Flushed {n} points")


@router.get("/history", response_model=Page[RealtimeOut], summary="[Admin] 即時資料歷史查詢")
async def history(
    metric: list[str] | None = Query(None),
    start: datetime | None = None,
    end: datetime | None = None,
    anomaly_only: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    _: User = Depends(require_perm(Perm.REALTIME_HISTORY)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(RealtimeData)
    if metric:
        stmt = stmt.where(RealtimeData.metric.in_(metric))
    if start:
        stmt = stmt.where(RealtimeData.timestamp >= to_naive_local(start))
    if end:
        stmt = stmt.where(RealtimeData.timestamp <= to_naive_local(end))
    if anomaly_only:
        stmt = stmt.where(RealtimeData.is_anomaly.is_(True))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    ts = RealtimeData.timestamp
    stmt = stmt.order_by(ts.asc() if order == "asc" else ts.desc(), RealtimeData.id.desc())
    items = (await db.scalars(stmt.offset((page - 1) * size).limit(size))).all()
    return Page(items=items, total=total, page=page, size=size, pages=math.ceil(total / size) if total else 0)


ws_router = APIRouter(tags=["Realtime"])


@ws_router.websocket("/ws/realtime")
async def realtime_ws(websocket: WebSocket, token: str = Query(...), metrics: str | None = Query(None)):
    """WebSocket 即時推送。連線：`ws://host/api/v1/ws/realtime?token=<JWT>&metrics=temperature,cpu_usage`

    伺服器訊息：
    - `{"type": "snapshot", "points": [...]}` 連線後的最近資料
    - `{"type": "tick", "points": [...], "alerts": [...]}` 每秒推送
    - `{"type": "pong"}` 回應客戶端 `{"action": "ping"}`

    客戶端可送 `{"action": "subscribe", "metrics": ["temperature"]}` 調整訂閱。
    """
    try:
        async with AsyncSessionLocal() as db:
            user = await get_user_from_token(token, db)
        if not has_perm(user.role, Perm.REALTIME_READ):
            raise AppException(403, "FORBIDDEN", "No realtime permission")
    except AppException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    client = Client(websocket, user.username, set(filter(None, (metrics or "").split(","))))
    await manager.connect(client)
    try:
        snapshot = generator.snapshot(300)
        if client.metrics:
            snapshot = [p for p in snapshot if p["metric"] in client.metrics]
        await websocket.send_json({"type": "snapshot", "points": snapshot})
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "invalid json"})
                continue
            if msg.get("action") == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg.get("action") == "subscribe":
                client.metrics = set(msg.get("metrics") or [])
                await websocket.send_json({"type": "subscribed", "metrics": sorted(client.metrics)})
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:  # noqa: BLE001
        pass
    finally:
        await manager.disconnect(client)
