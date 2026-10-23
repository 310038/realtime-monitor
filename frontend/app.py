"""Streamlit 進入點：依登入狀態與角色動態組成多頁面導覽。"""
import streamlit as st

from utils import auth
from utils.config import PUBLIC_API_URL

st.set_page_config(page_title="即時資料分析與監控系統", page_icon="📡", layout="wide")

if st.session_state.pop("auth_expired", False):
    st.toast("登入已過期，請重新登入", icon="⚠️")

if not auth.is_logged_in():
    pg = st.navigation([st.Page("views/login.py", title="登入 / 註冊", icon="🔐")])
    pg.run()
    st.stop()

user = auth.current_user()
pages = {
    "總覽": [st.Page("views/dashboard.py", title="儀表板", icon="🏠", default=True)],
    "資料": [
        st.Page("views/realtime.py", title="即時監控", icon="📡"),
        st.Page("views/records.py", title="資料管理", icon="📋"),
        st.Page("views/analytics.py", title="資料分析", icon="📊"),
    ],
    "帳號": [st.Page("views/profile.py", title="個人資料", icon="👤")],
}
if auth.can("admin"):
    pages["系統管理"] = [st.Page("views/admin.py", title="系統管理", icon="🛠️")]

with st.sidebar:
    st.markdown(f"**👋 {user.get('full_name') or user['username']}**")
    st.caption(f"角色：{auth.ROLE_LABELS.get(user['role'], user['role'])}　|　{user['email']}")
    if st.button("登出", icon="🚪", use_container_width=True):
        auth.logout()
        st.rerun()
    st.divider()
    st.link_button("📘 API 文件 (Swagger)", f"{PUBLIC_API_URL}/docs", use_container_width=True)

pg = st.navigation(pages)
pg.run()
