"""應用程式設定：全部由環境變數（或 .env）載入。"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "Realtime Monitor API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    CORS_ORIGINS: list[str] = ["*"]

    # --- Database (MariaDB + asyncmy) ---
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "monitor"
    DB_PASSWORD: str = "monitor_pass"
    DB_NAME: str = "monitor"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False
    # 測試時可直接覆寫整條連線字串（例如 sqlite+aiosqlite）
    DATABASE_URL_OVERRIDE: str | None = None

    # --- JWT ---
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # --- Seed accounts ---
    SEED_DEFAULT_USERS: bool = True
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "Admin@123"
    ADMIN_EMAIL: str = "admin@example.com"
    DEMO_USER_PASSWORD: str = "User@123"
    DEMO_VIEWER_PASSWORD: str = "Viewer@123"
    SEED_SAMPLE_DATA: bool = True
    SAMPLE_DATA_PATH: str = str(Path(__file__).resolve().parents[3] / "sample_data" / "records.csv")

    # --- Realtime generator & batch writer ---
    GENERATOR_ENABLED: bool = True
    GENERATOR_INTERVAL_SECONDS: float = 1.0
    REALTIME_METRICS: list[str] = ["temperature", "humidity", "cpu_usage", "pressure"]
    BATCH_FLUSH_INTERVAL_SECONDS: int = 10  # 定期觸發
    BATCH_MAX_SIZE: int = 50  # 條件觸發：緩衝區達到此數量立即寫入
    FLUSH_ON_ANOMALY: bool = True  # 條件觸發：出現異常值時立即寫入

    # 預設告警閾值（可由 Admin 透過 API 調整）
    DEFAULT_THRESHOLD: float = 90.0
    THRESHOLDS: dict[str, float] = Field(
        default_factory=lambda: {
            "temperature": 35.0,
            "humidity": 85.0,
            "cpu_usage": 90.0,
            "pressure": 1030.0,
            "sales": 5000.0,
            "traffic": 800.0,
        }
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        return (
            f"mysql+asyncmy://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
