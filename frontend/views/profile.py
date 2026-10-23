import streamlit as st

from utils import api, auth

st.title("👤 個人資料")
user = auth.current_user()

c1, c2 = st.columns(2)
with c1:
    st.markdown(
        f"- **帳號**：{user['username']}\n- **Email**：{user['email']}\n"
        f"- **角色**：{auth.ROLE_LABELS.get(user['role'])}\n- **建立時間**：{user['created_at']}"
    )
    st.markdown("**角色權限**")
    st.write(", ".join(f"`{p}`" for p in st.session_state.get("permissions", [])))

with c2:
    with st.form("profile"):
        full_name = st.text_input("姓名", value=user.get("full_name") or "")
        email = st.text_input("Email", value=user["email"])
        pwd = st.text_input("新密碼（不修改請留空）", type="password")
        if st.form_submit_button("儲存", type="primary"):
            body = {"full_name": full_name or None, "email": email}
            if pwd:
                body["password"] = pwd
            try:
                st.session_state["user"] = api.patch("/users/me", json=body)
                st.success("已更新")
                st.rerun()
            except api.ApiError as e:
                api.show_error(e)
