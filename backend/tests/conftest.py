"""測試以 SQLite（aiosqlite）取代 MariaDB，邏輯同樣全部走 SQLAlchemy ORM。"""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="rtm-test-"))
os.environ.update(
    DATABASE_URL_OVERRIDE=f"sqlite+aiosqlite:///{_tmp / 'test.db'}",
    GENERATOR_ENABLED="false",
    GENERATOR_INTERVAL_SECONDS="0.2",
    BATCH_FLUSH_INTERVAL_SECONDS="60",
    SEED_SAMPLE_DATA="false",
    LOG_DIR=str(_tmp / "logs"),
    LOG_LEVEL="WARNING",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402,F401
from app.main import app  # noqa: E402

PASSWORDS = {"admin": "Admin@123", "user": "User@123", "viewer": "Viewer@123"}


@pytest.fixture(scope="session")
def client():
    sync_engine = create_engine(f"sqlite:///{_tmp / 'test.db'}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, username: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_h(client):
    return _login(client, "admin", PASSWORDS["admin"])


@pytest.fixture(scope="session")
def user_h(client):
    return _login(client, "user", PASSWORDS["user"])


@pytest.fixture(scope="session")
def viewer_h(client):
    return _login(client, "viewer", PASSWORDS["viewer"])


@pytest.fixture(scope="session")
def login():
    return _login
