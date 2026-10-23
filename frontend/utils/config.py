import os

# Streamlit 伺服器 -> 後端（容器內網路）
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
# 給使用者瀏覽器開啟的 Swagger 連結
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
WS_BASE_URL = os.getenv("WS_BASE_URL", API_BASE_URL.replace("https://", "wss://").replace("http://", "ws://"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15"))
