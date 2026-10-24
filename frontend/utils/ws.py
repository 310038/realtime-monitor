"""背景 WebSocket 用戶端：在獨立執行緒接收推送資料，存放於 thread-safe deque。

Streamlit 在使用者關閉分頁時不會通知背景執行緒，因此以「閒置逾時」自我回收：
頁面每次重繪呼叫 touch()，超過 IDLE_TIMEOUT 秒沒有被讀取就斷線結束；
再次進入即時監控頁時 start() 會重新連線。
"""
import json
import os
import threading
import time
from collections import deque

import websocket

from utils.config import WS_BASE_URL

IDLE_TIMEOUT = float(os.getenv("WS_IDLE_TIMEOUT", "60"))


class RealtimeStream:
    def __init__(self, token: str, maxlen: int = 4 * 900):
        self.token = token
        self.points: deque[dict] = deque(maxlen=maxlen)
        self.alerts: deque[dict] = deque(maxlen=200)
        self.connected = False
        self.last_error: str | None = None
        self.last_message_at: float | None = None
        self.received = 0
        self.last_read_at = time.time()
        self._stop = threading.Event()
        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def touch(self) -> None:
        """頁面讀取資料時呼叫，表示仍有人在看。"""
        self.last_read_at = time.time()

    @property
    def idle(self) -> bool:
        return time.time() - self.last_read_at > IDLE_TIMEOUT

    def start(self) -> None:
        self.touch()
        if self.alive:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="rt-ws")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:  # noqa: BLE001
                pass

    def _on_open(self, _ws):
        self.connected = True
        self.last_error = None

    def _on_message(self, _ws, raw: str):
        msg = json.loads(raw)
        self.last_message_at = time.time()
        if msg.get("type") == "snapshot":
            self.points.extend(msg.get("points", []))
        elif msg.get("type") == "tick":
            self.received += 1
            self.points.extend(msg.get("points", []))
            self.alerts.extend(msg.get("alerts", []))

    def _on_error(self, _ws, err):
        self.last_error = str(err)

    def _on_close(self, _ws, code, reason):
        self.connected = False
        if code == 1008:
            self.last_error = "Token 無效或沒有權限"
            self._stop.set()

    def _run(self) -> None:
        url = f"{WS_BASE_URL}/api/v1/ws/realtime?token={self.token}"
        while not self._stop.is_set():
            self._ws = websocket.WebSocketApp(
                url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            conn = threading.Thread(
                target=self._ws.run_forever, kwargs={"ping_interval": 20, "ping_timeout": 10}, daemon=True
            )
            conn.start()
            while conn.is_alive():
                if self.idle:  # 分頁已關閉或離開即時監控頁
                    self.stop()
                conn.join(1)
            self.connected = False
            if self._stop.wait(3):  # 斷線 3 秒後自動重連
                break
