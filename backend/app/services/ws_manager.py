"""WebSocket 連線管理與廣播。"""
import asyncio
import logging
from dataclasses import dataclass, field

from fastapi import WebSocket

logger = logging.getLogger("app.ws")


@dataclass(eq=False)
class Client:
    websocket: WebSocket
    username: str
    metrics: set[str] = field(default_factory=set)  # 空集合代表訂閱全部


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[Client] = set()
        self._lock = asyncio.Lock()

    @property
    def count(self) -> int:
        return len(self._clients)

    async def connect(self, client: Client) -> None:
        await client.websocket.accept()
        async with self._lock:
            self._clients.add(client)
        logger.info("WS connected: %s (total=%d)", client.username, self.count)

    async def disconnect(self, client: Client) -> None:
        async with self._lock:
            self._clients.discard(client)
        logger.info("WS disconnected: %s (total=%d)", client.username, self.count)

    async def broadcast(self, message: dict) -> None:
        if not self._clients:
            return
        dead: list[Client] = []
        for client in list(self._clients):
            payload = message
            if client.metrics and "points" in message:
                points = [p for p in message["points"] if p["metric"] in client.metrics]
                alerts = [p for p in message.get("alerts", []) if p["metric"] in client.metrics]
                payload = {**message, "points": points, "alerts": alerts}
            try:
                await client.websocket.send_json(payload)
            except Exception:  # noqa: BLE001
                dead.append(client)
        for client in dead:
            await self.disconnect(client)


manager = ConnectionManager()
