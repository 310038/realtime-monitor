import json


def _create(client, headers, **kw):
    payload = {"title": "t", "value": 10, "category": "sales", **kw}
    r = client.post("/api/v1/records", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_crud_and_permissions(client, admin_h, user_h, viewer_h, login):
    rec = _create(client, user_h, title="Mine", value=12.5, category="sales")
    assert rec["owner_username"] == "user"

    # viewer 唯讀
    assert client.post("/api/v1/records", json={"title": "x", "value": 1, "category": "c"}, headers=viewer_h).status_code == 403
    assert client.get(f"/api/v1/records/{rec['id']}", headers=viewer_h).status_code == 200
    assert client.patch(f"/api/v1/records/{rec['id']}", json={"value": 1}, headers=viewer_h).status_code == 403

    # 其他 user 不能改/刪
    client.post("/api/v1/auth/register", json={"username": "bob", "email": "bob@example.com", "password": "secret123"})
    bob_h = login(client, "bob", "secret123")
    assert client.patch(f"/api/v1/records/{rec['id']}", json={"value": 1}, headers=bob_h).status_code == 403
    assert client.delete(f"/api/v1/records/{rec['id']}", headers=bob_h).status_code == 403

    # 建立者可以 PATCH / PUT
    r = client.patch(f"/api/v1/records/{rec['id']}", json={"value": 99}, headers=user_h)
    assert r.status_code == 200 and r.json()["value"] == 99
    r = client.put(
        f"/api/v1/records/{rec['id']}",
        json={"title": "Full", "value": 5, "category": "sales", "description": "d"},
        headers=user_h,
    )
    assert r.status_code == 200 and r.json()["title"] == "Full"

    # Admin 可以改任何人的資料
    assert client.patch(f"/api/v1/records/{rec['id']}", json={"title": "by admin"}, headers=admin_h).status_code == 200
    assert client.delete(f"/api/v1/records/{rec['id']}", headers=user_h).status_code == 204
    assert client.get(f"/api/v1/records/{rec['id']}", headers=user_h).status_code == 404


def test_anomaly_flag_uses_threshold(client, user_h):
    hot = _create(client, user_h, title="hot", value=40, category="temperature")  # 閾值 35
    cold = _create(client, user_h, title="cold", value=20, category="temperature")
    assert hot["is_anomaly"] is True and cold["is_anomaly"] is False


def test_list_paging_filter_sort(client, user_h):
    for i in range(5):
        _create(client, user_h, title=f"page-{i}", value=i, category="paging", timestamp=f"2026-01-0{i + 1}T10:00:00")
    r = client.get(
        "/api/v1/records",
        params={"category": "paging", "size": 2, "page": 1, "sort_by": "value", "order": "asc"},
        headers=user_h,
    )
    body = r.json()
    assert body["total"] == 5 and body["pages"] == 3
    assert [x["value"] for x in body["items"]] == [0, 1]

    r = client.get(
        "/api/v1/records",
        params={"category": "paging", "start": "2026-01-02T00:00:00", "end": "2026-01-04T23:59:59", "min_value": 2},
        headers=user_h,
    )
    assert {x["title"] for x in r.json()["items"]} == {"page-2", "page-3"}

    r = client.get("/api/v1/records", params={"keyword": "page-4"}, headers=user_h)
    assert r.json()["total"] == 1


def test_import_csv_and_json(client, user_h, viewer_h):
    csv_body = (
        "title,value,category,timestamp,description\n"
        "A,1.5,import,2026-02-01T08:00:00,ok\n"
        "B,not-a-number,import,,bad\n"
        "C,3,import,2026-02-01 09:00:00,\n"
    )
    r = client.post("/api/v1/records/import", files={"file": ("d.csv", csv_body, "text/csv")}, headers=user_h)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2 and r.json()["failed"] == 1 and r.json()["errors"][0]["row"] == 3

    data = json.dumps([{"title": "J1", "value": 7, "category": "import-json"}, {"title": "missing value"}])
    r = client.post("/api/v1/records/import", files={"file": ("d.json", data, "application/json")}, headers=user_h)
    assert r.json()["imported"] == 1 and r.json()["failed"] == 1

    r = client.post("/api/v1/records/import", files={"file": ("d.txt", "x", "text/plain")}, headers=user_h)
    assert r.status_code == 400
    r = client.post("/api/v1/records/import", files={"file": ("d.csv", csv_body, "text/csv")}, headers=viewer_h)
    assert r.status_code == 403
