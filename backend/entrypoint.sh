#!/bin/sh
set -e

# 等待 DB 並執行 Alembic 遷移（最多重試 30 次）
i=0
until alembic upgrade head; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then
    echo "Database migration failed after $i attempts" >&2
    exit 1
  fi
  echo "Waiting for database... ($i)"
  sleep 2
done

# 單一 worker：即時產生器與 WebSocket 連線管理為行程內單例
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' "$@"
