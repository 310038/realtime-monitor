"""後端 REST API 用戶端（自動帶入 JWT、統一錯誤處理）。"""
from typing import Any

import requests
import streamlit as st

from utils.config import API_BASE_URL, REQUEST_TIMEOUT


class ApiError(Exception):
    def __init__(self, status: int, message: str, details: Any = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details


def _headers() -> dict:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def request(method: str, path: str, *, raw: bool = False, **kwargs) -> Any:
    url = f"{API_BASE_URL}/api/v1{path}"
    try:
        resp = requests.request(method, url, headers=_headers(), timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.RequestException as e:
        raise ApiError(0, f"無法連線到後端：{e}") from e

    if resp.status_code == 401 and st.session_state.get("token"):
        # Token 過期或帳號被停用：清除登入狀態
        st.session_state["auth_expired"] = True
        st.session_state.pop("token", None)
        st.session_state.pop("user", None)

    if resp.status_code >= 400:
        try:
            err = resp.json().get("error", {})
            raise ApiError(resp.status_code, err.get("message", resp.text), err.get("details"))
        except ValueError:
            raise ApiError(resp.status_code, resp.text)
    if raw:
        return resp
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


def get(path: str, **kw):
    return request("GET", path, **kw)


def post(path: str, **kw):
    return request("POST", path, **kw)


def put(path: str, **kw):
    return request("PUT", path, **kw)


def patch(path: str, **kw):
    return request("PATCH", path, **kw)


def delete(path: str, **kw):
    return request("DELETE", path, **kw)


def show_error(e: ApiError) -> None:
    msg = f"[{e.status}] {e.message}" if e.status else e.message
    st.error(msg)
    if e.details:
        with st.expander("錯誤細節"):
            st.json(e.details)


def clean_params(params: dict) -> dict:
    return {k: v for k, v in params.items() if v not in (None, "", [])}
