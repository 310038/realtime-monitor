# 系統架構

![architecture](architecture.svg)

## 元件關係

```mermaid
flowchart LR
    U["使用者瀏覽器<br/>Admin / User / Viewer"]

    subgraph Docker["Docker Compose"]
        subgraph FN["frontend-net"]
            FE["frontend<br/>Streamlit :8501<br/>多頁面 · Session State"]
        end
        subgraph BN["backend-net"]
            BE["backend<br/>FastAPI :8000<br/>REST · WebSocket · JWT/RBAC"]
            GEN["DataGenerator<br/>(asyncio, 每秒)"]
            BW["BatchWriter<br/>定期 / 條件觸發"]
            DB[("MariaDB 11.7<br/>:3306")]
        end
        V1[["volume: db_data"]]
        V2[["volume: backend_logs"]]
    end

    U -- "HTTP :8501" --> FE
    U -. "Swagger :8000/docs" .-> BE
    FE -- "REST + JWT" --> BE
    BE -- "WebSocket 推送" --> FE
    GEN --> BE
    GEN --> BW
    BE -- "SQLAlchemy ORM (asyncmy)" --> DB
    BW -- "批次 INSERT (ORM add_all)" --> DB
    DB --- V1
    BE --- V2
```

## 即時資料流程

```mermaid
sequenceDiagram
    participant G as DataGenerator
    participant M as ConnectionManager
    participant W as BatchWriter
    participant DB as MariaDB
    participant S as Streamlit (ws 執行緒)
    participant UI as 即時監控頁 (st.fragment)

    S->>M: 連線 /api/v1/ws/realtime?token=JWT
    M-->>S: snapshot（最近 300 點）
    loop 每 1 秒
        G->>G: 產生各指標數值，與閾值比對標記 is_anomaly
        G->>M: broadcast {type: tick, points, alerts}
        M-->>S: 推送
        G->>W: add(points)
        alt 緩衝區 >= BATCH_MAX_SIZE 或 有異常值
            W->>DB: 立即批次寫入（條件觸發）
        end
    end
    loop 每 BATCH_FLUSH_INTERVAL_SECONDS
        W->>DB: 批次寫入（定期觸發）
    end
    loop 每 1~5 秒
        UI->>S: 讀取 deque，重繪折線圖 / 柱狀圖 / 告警
    end
```

## 資料模型

```mermaid
erDiagram
    users ||--o{ data_records : "owner_id"
    users {
        int id PK
        string username UK
        string email UK
        enum role "admin | user | viewer"
        bool is_active
        string hashed_password
    }
    data_records {
        int id PK
        string title
        float value
        string category
        datetime timestamp
        text description
        bool is_anomaly
        int owner_id FK
    }
    realtime_data {
        int id PK
        string metric
        float value
        float threshold
        bool is_anomaly
        datetime timestamp
    }
    metric_thresholds {
        int id PK
        string name UK
        float threshold
    }
    system_logs {
        int id PK
        string level
        string category
        text message
        string username
        string path
        int status_code
        float duration_ms
        datetime created_at
    }
```

## 設計重點

| 主題 | 做法 |
|---|---|
| ORM | 所有查詢、聚合、時間分桶皆以 SQLAlchemy 2.0 `select()` / `func.*` 表達，無原生 SQL 字串 |
| 非同步 | `create_async_engine("mysql+asyncmy://...")` + `AsyncSession`；API、產生器、批次寫入全為 async |
| 連接池 | `pool_size`、`max_overflow`、`pool_recycle`、`pool_pre_ping` 皆由環境變數控制，`/admin/db-status` 可即時觀察 |
| 遷移 | Alembic（async env），容器啟動時 `alembic upgrade head` |
| 批次寫入 | 記憶體緩衝；定期（每 N 秒）、條件（滿 N 筆 / 出現異常）、關機前 flush；DB 失敗時重新排入 |
| 權限 | Role → Permission 對照表（`app/core/permissions.py`），以 `require_perm()` 依賴注入檢查；資料修改另檢查擁有者 |
| 日誌 | stdout + 輪替檔（`backend_logs` volume）+ `system_logs` 表（存取 / 認證 / 資料異動 / 告警） |
| 擴展性 | 產生器與 WS 管理為行程內單例，故 uvicorn 以單一 worker 執行；如需水平擴展，可將產生器獨立成服務並以 Redis Pub/Sub 廣播 |
