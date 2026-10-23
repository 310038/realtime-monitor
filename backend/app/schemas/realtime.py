from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RealtimePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric: str
    value: float
    threshold: float
    is_anomaly: bool
    timestamp: datetime


class RealtimeOut(RealtimePoint):
    id: int


class ThresholdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    threshold: float
    updated_at: datetime


class ThresholdUpsert(BaseModel):
    threshold: float = Field(..., description="超過此值即標記異常")


class GeneratorStatus(BaseModel):
    running: bool
    metrics: list[str]
    interval_seconds: float
    buffer_size: int
    batch_max_size: int
    flush_interval_seconds: int
    total_generated: int
    total_flushed: int
    last_flush_at: datetime | None
    last_flush_reason: str | None
    websocket_clients: int
