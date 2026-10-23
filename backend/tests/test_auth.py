def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["database"] is True


def test_register_login_me(client, login):
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123", "full_name": "Alice"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "user"

    dup = client.post(
        "/api/v1/auth/register", json={"username": "alice", "email": "x@example.com", "password": "secret123"}
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "CONFLICT"

    headers = login(client, "alice", "secret123")
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["username"] == "alice"


def test_login_wrong_password(client):
    r = client.post("/api/v1/auth/login", data={"username": "admin", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_requires_token(client):
    assert client.get("/api/v1/records").status_code == 401
    bad = client.get("/api/v1/records", headers={"Authorization": "Bearer invalid"})
    assert bad.status_code == 401


def test_validation_error_format(client):
    r = client.post("/api/v1/auth/register", json={"username": "x", "email": "bad", "password": "1"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "VALIDATION_ERROR" and body["details"]
