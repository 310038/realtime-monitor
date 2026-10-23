"""背景 WebSocket 用戶端：在獨立執行緒接收推送資料，存放於 thread-safe deque。"""
import json
import threading
import time
from collections import deque

import websocket

from utils.config import WS_BASE_URL


class RealtimeStream:
    def __init__(self, token: str, maxlen: int = 4 * 900):
        self.token = token
        self.points: deque[dict] = deque(maxlen=maxlen)
        self.alerts: deque[dict] = deque(maxlen=200)
        self.connected = False
        self.last_error: str | None = None
        self.last_message_at: float | None = None
        self.received = 0
        self._stop = threading.Event()
        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
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
            self._ws.run_forever(ping_interval=20, ping_timeout=10)
            self.connected = False
            if not self._stop.wait(3):  # 斷線 3 秒後自動重連
                continue
