import streamlit as st

from utils import api, auth

st.title("📡 即時資料分析與監控系統")
st.caption("FastAPI · WebSocket · MariaDB · Streamlit")

col, _ = st.columns([1, 1])
with col:
    tab_login, tab_register = st.tabs(["登入", "註冊"])

    with tab_login:
        with st.form("login"):
            username = st.text_input("帳號")
            password = st.text_input("密碼", type="password")
            submitted = st.form_submit_button("登入", type="primary", use_container_width=True)
        if submitted:
            try:
                auth.login(username, password)
                st.rerun()
            except api.ApiError as e:
                api.show_error(e)
        with st.expander("測試帳號"):
            st.markdown(
                "| 角色 | 帳號 | 密碼 |\n|---|---|---|\n"
                "| Admin | `admin` | `Admin@123` |\n"
                "| User | `user` | `User@123` |\n"
                "| Viewer | `viewer` | `Viewer@123` |"
            )

    with tab_register:
        with st.form("register"):
            r_user = st.text_input("帳號（3-50 字元，英數字與 _ . -）")
            r_email = st.text_input("Email")
            r_name = st.text_input("姓名（選填）")
            r_pwd = st.text_input("密碼（至少 6 碼）", type="password")
            r_pwd2 = st.text_input("確認密碼", type="password")
            reg = st.form_submit_button("註冊", use_container_width=True)
        if reg:
            if r_pwd != r_pwd2:
                st.error("兩次密碼不一致")
            else:
                try:
                    api.post(
                        "/auth/register",
                        json={"username": r_user, "email": r_email, "full_name": r_name or None, "password": r_pwd},
                    )
                    st.success("註冊成功（角色：user），請切換到「登入」分頁登入。")
                except api.ApiError as e:
                    api.show_error(e)
