"""登入狀態（Session State）管理。"""
import streamlit as st

from utils import api

ROLE_LABELS = {"admin": "管理員", "user": "一般使用者", "viewer": "檢視者"}


def is_logged_in() -> bool:
    return bool(st.session_state.get("token") and st.session_state.get("user"))


def current_user() -> dict:
    return st.session_state.get("user") or {}


def role() -> str | None:
    return current_user().get("role")


def can(*roles: str) -> bool:
    return role() in roles


def login(username: str, password: str) -> None:
    data = api.post("/auth/login", data={"username": username, "password": password})
    st.session_state["token"] = data["access_token"]
    st.session_state["user"] = data["user"]
    st.session_state.pop("auth_expired", None)
    try:
        st.session_state["permissions"] = api.get("/users/me/permissions")
    except api.ApiError:
        st.session_state["permissions"] = []


def logout() -> None:
    try:
        if st.session_state.get("token"):
            api.post("/auth/logout")
    except api.ApiError:
        pass
    stream = st.session_state.get("rt_stream")
    if stream:
        stream.stop()
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def require_role(*roles: str) -> None:
    if not can(*roles):
        st.error("您的角色沒有權限瀏覽此頁面。")
        st.stop()
