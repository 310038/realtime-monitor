from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RecordBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, examples=["Sensor A reading"])
    value: float = Field(..., examples=[42.5])
    category: str = Field(..., min_length=1, max_length=50, examples=["temperature"])
    timestamp: datetime | None = Field(None, description="未提供時以伺服器時間為準")
    description: str | None = Field(None, max_length=2000)


class RecordCreate(RecordBase):
    pass


class RecordUpdate(BaseModel):
    """PUT/PATCH 皆使用：只更新有給的欄位。"""

    title: str | None = Field(None, min_length=1, max_length=200)
    value: float | None = None
    category: str | None = Field(None, min_length=1, max_length=50)
    timestamp: datetime | None = None
    description: str | None = Field(None, max_length=2000)


class RecordOut(RecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    is_anomaly: bool
    owner_id: int | None
    owner_username: str | None = None
    created_at: datetime
    updated_at: datetime


class SortField(str, Enum):
    id = "id"
    title = "title"
    value = "value"
    category = "category"
    timestamp = "timestamp"
    created_at = "created_at"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class ImportResult(BaseModel):
    total: int
    imported: int
    failed: int
    anomalies: int
    errors: list[dict]
