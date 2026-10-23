"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-23 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100)),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "user", "viewer", name="user_role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "data_records",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_data_records_category", "data_records", ["category"])
    op.create_index("ix_data_records_timestamp", "data_records", ["timestamp"])
    op.create_index("ix_data_records_owner_id", "data_records", ["owner_id"])
    op.create_index("ix_data_records_category_ts", "data_records", ["category", "timestamp"])

    op.create_table(
        "realtime_data",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_realtime_data_is_anomaly", "realtime_data", ["is_anomaly"])
    op.create_index("ix_realtime_data_timestamp", "realtime_data", ["timestamp"])
    op.create_index("ix_realtime_metric_ts", "realtime_data", ["metric", "timestamp"])

    op.create_table(
        "metric_thresholds",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("threshold", sa.Float(), nullable=False),
        *_timestamps(),
        mysql_charset="utf8mb4",
    )

    op.create_table(
        "system_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("username", sa.String(50)),
        sa.Column("method", sa.String(10)),
        sa.Column("path", sa.String(255)),
        sa.Column("status_code", sa.Integer()),
        sa.Column("duration_ms", sa.Float()),
        sa.Column("client_ip", sa.String(64)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_system_logs_level", "system_logs", ["level"])
    op.create_index("ix_system_logs_category", "system_logs", ["category"])
    op.create_index("ix_system_logs_username", "system_logs", ["username"])
    op.create_index("ix_system_logs_created_at", "system_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("system_logs")
    op.drop_table("metric_thresholds")
    op.drop_table("realtime_data")
    op.drop_table("data_records")
    op.drop_table("users")
