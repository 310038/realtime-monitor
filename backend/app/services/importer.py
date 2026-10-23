"""CSV / JSON 批量匯入解析與驗證。"""
import csv
import io
import json

from pydantic import ValidationError

from app.core.timeutil import now, to_naive_local
from app.schemas.record import RecordCreate

REQUIRED = {"title", "value", "category"}


def _validate(raw: dict, row_no: int, ok: list[RecordCreate], errors: list[dict]) -> None:
    cleaned = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items() if k}
    cleaned = {k: v for k, v in cleaned.items() if v not in ("", None)}
    try:
        rec = RecordCreate(**cleaned)
    except ValidationError as e:
        errors.append({"row": row_no, "errors": [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()]})
        return
    rec.timestamp = to_naive_local(rec.timestamp) or now()
    ok.append(rec)


def parse_csv(content: bytes) -> tuple[list[RecordCreate], list[dict]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    missing = REQUIRED - headers
    if missing:
        return [], [{"row": 0, "errors": [f"Missing columns: {', '.join(sorted(missing))}"]}]
    ok: list[RecordCreate] = []
    errors: list[dict] = []
    for i, row in enumerate(reader, start=2):  # 第 1 列為表頭
        _validate(row, i, ok, errors)
    return ok, errors


def parse_json(content: bytes) -> tuple[list[RecordCreate], list[dict]]:
    try:
        data = json.loads(content.decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return [], [{"row": 0, "errors": [f"Invalid JSON: {e}"]}]
    if isinstance(data, dict):
        data = data.get("records", [])
    if not isinstance(data, list):
        return [], [{"row": 0, "errors": ["JSON must be a list or {\"records\": [...]}"]}]
    ok: list[RecordCreate] = []
    errors: list[dict] = []
    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            errors.append({"row": i, "errors": ["Item must be an object"]})
            continue
        _validate(item, i, ok, errors)
    return ok, errors
