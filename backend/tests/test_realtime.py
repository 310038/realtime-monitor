import time

import pytest
from starlette.websockets import WebSocketDisconnect

from app.services.generator import DataGenerator


def test_generate_tick_marks_anomalies():
    g = DataGenerator()
    points = [p for _ in range(300) for p in g.generate_tick()]
    assert {p["metric"] for p in points} == {"temperature", "humidity", "cpu_usage", "pressure"}
    assert all(p["is_anomaly"] == (p["value"] > p["threshold"]) for p in points)
    assert any(p["is_anomaly"] for p in points)


def test_websocket_requires_valid_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws/realtime?token=bad") as ws:
            ws.receive_json()


def test_generator_ws_and_batch_write(client, admin_h, viewer_h):
    assert client.post("/api/v1/realtime/generator/start", headers=viewer_h).status_code == 403
    assert client.post("/api/v1/realtime/generator/start", headers=admin_h).json()["running"] is True

    token = viewer_h["Authorization"].split()[1]
    with client.websocket_connect(f"/api/v1/ws/realtime?token={token}&metrics=temperature") as ws:
        assert ws.receive_json()["type"] == "snapshot"
        tick = ws.receive_json()
        assert tick["type"] == "tick"
        assert {p["metric"] for p in tick["points"]} == {"temperature"}
        ws.send_json({"action": "ping"})
        msg = ws.receive_json()
        while msg["type"] != "pong":
            msg = ws.receive_json()

    time.sleep(0.5)
    client.post("/api/v1/realtime/generator/stop", headers=admin_h)
    status = client.get("/api/v1/realtime/status", headers=viewer_h).json()
    assert status["running"] is False and status["buffer_size"] == 0 and status["total_flushed"] > 0

    hist = client.get("/api/v1/realtime/history", params={"metric": "cpu_usage"}, headers=admin_h).json()
    assert hist["total"] > 0 and all(i["metric"] == "cpu_usage" for i in hist["items"])

    summary = client.get("/api/v1/analytics/realtime/summary", headers=viewer_h).json()
    assert {s["metric"] for s in summary} >= {"temperature", "cpu_usage"}
