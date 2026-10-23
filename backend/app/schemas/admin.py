from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SystemLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level: str
    category: str
    message: str
    username: str | None
    method: str | None
    path: str | None
    status_code: int | None
    duration_ms: float | None
    client_ip: str | None
    created_at: datetime


class PoolStatus(BaseModel):
    pool_class: str
    size: int | None
    checked_in: int | None
    checked_out: int | None
    overflow: int | None
    status: str


class DatabaseStatus(BaseModel):
    connected: bool
    dialect: str
    server_version: str | None
    latency_ms: float | None
    pool: PoolStatus
    table_counts: dict[str, int]
    checked_at: datetime
