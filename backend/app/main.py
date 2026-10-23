"""FastAPI 應用程式進入點。"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal, engine
from app.services.audit import log_in_background
from app.services.batch_writer import batch_writer
from app.services.generator import generator
from app.services.seed import seed

setup_logging()
logger = logging.getLogger("app")

SKIP_LOG_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json", "/api/v1/ws")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s (%s)", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    async with AsyncSessionLocal() as session:
        await seed(session)
    batch_writer.start()
    if settings.GENERATOR_ENABLED:
        generator.start()
    yield
    await generator.stop()
    await batch_writer.stop()
    await engine.dispose()
    logger.info("Shutdown complete")


TAGS = [
    {"name": "Auth", "description": "註冊、登入（JWT）、登出"},
    {"name": "Users", "description": "個人資料與使用者權限管理（Admin）"},
    {"name": "Records", "description": "資料記錄 CRUD、分頁 / 篩選 / 排序、CSV/JSON 批量匯入"},
    {"name": "Analytics", "description": "統計分析、分類聚合、趨勢、Excel 匯出"},
    {"name": "Realtime", "description": "即時資料產生器、WebSocket 推送、歷史查詢"},
    {"name": "Thresholds", "description": "告警閾值設定"},
    {"name": "Admin", "description": "系統日誌、資料庫狀態"},
]

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "即時資料分析與監控系統 API。\n\n"
        "1. 先以 `POST /api/v1/auth/login` 取得 Token，或點右上角 **Authorize**。\n"
        "2. 角色：`admin`（全部權限）/ `user`（建立、修改與刪除自己的資料）/ `viewer`（唯讀）。\n"
        "3. WebSocket：`/api/v1/ws/realtime?token=<JWT>`。"
    ),
    openapi_tags=TAGS,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/") and not path.startswith(SKIP_LOG_PREFIXES):
        duration = round((time.perf_counter() - start) * 1000, 2)
        level = "ERROR" if response.status_code >= 500 else "WARNING" if response.status_code >= 400 else "INFO"
        username = getattr(request.state, "username", None)
        logger.log(
            logging.getLevelName(level), "%s %s -> %s (%.1fms) user=%s",
            request.method, path, response.status_code, duration, username,
        )
        log_in_background(
            f"{request.method} {path} -> {response.status_code}",
            level=level,
            category="request",
            username=username,
            method=request.method,
            path=path[:255],
            status_code=response.status_code,
            duration_ms=duration,
            client_ip=request.client.host if request.client else None,
        )
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - start) * 1000:.2f}"
    return response


app.include_router(api_router)


@app.get("/health", tags=["Health"], summary="健康檢查（含 DB 連線）")
async def health():
    db_ok = True
    try:
        async with AsyncSessionLocal() as session:
            await session.scalar(select(1))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "generator": generator.running}
