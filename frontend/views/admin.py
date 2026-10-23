from datetime import date, datetime, time, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import api, auth

auth.require_role("admin")
st.title("🛠️ 系統管理")
me = auth.current_user()

tabs = st.tabs(["👥 使用者", "📜 系統日誌", "🗄️ 資料庫狀態", "🕘 即時歷史資料", "🚨 告警閾值"])

# ---------------- 使用者 ----------------
with tabs[0]:
    c1, c2, c3 = st.columns(3)
    search = c1.text_input("搜尋（帳號 / Email / 姓名）")
    role_f = c2.selectbox("角色", ["全部", "admin", "user", "viewer"])
    page = c3.number_input("頁碼", min_value=1, value=1, key="u_page")
    try:
        users = api.get(
            "/users",
            params=api.clean_params({"search": search, "role": None if role_f == "全部" else role_f, "page": page, "size": 50}),
        )
    except api.ApiError as e:
        api.show_error(e)
        st.stop()
    st.caption(f"共 {users['total']} 位使用者")
    udf = pd.DataFrame(users["items"])
    if not udf.empty:
        st.dataframe(udf[["id", "username", "email", "full_name", "role", "is_active", "created_at"]], hide_index=True, use_container_width=True)

        st.markdown("#### 權限管理")
        options = {f"#{u['id']} {u['username']} ({u['role']})": u for u in users["items"]}
        target = options[st.selectbox("選擇使用者", list(options))]
        with st.form("role"):
            r1, r2 = st.columns(2)
            roles = ["admin", "user", "viewer"]
            new_role = r1.selectbox("角色", roles, index=roles.index(target["role"]), format_func=lambda r: f"{r}（{auth.ROLE_LABELS[r]}）")
            active = r2.toggle("啟用", value=target["is_active"])
            b1, b2 = st.columns(2)
            save = b1.form_submit_button("💾 儲存", type="primary")
            remove = b2.form_submit_button("🗑️ 刪除使用者", disabled=target["id"] == me["id"])
        if save:
            try:
                api.patch(f"/users/{target['id']}", json={"role": new_role, "is_active": active})
                st.success("已更新")
                st.rerun()
            except api.ApiError as e:
                api.show_error(e)
        if remove:
            try:
                api.delete(f"/users/{target['id']}")
                st.success("已刪除")
                st.rerun()
            except api.ApiError as e:
                api.show_error(e)
        with st.expander("角色權限說明"):
            st.markdown(
                "| 功能 | Admin | User | Viewer |\n|---|:-:|:-:|:-:|\n"
                "| 檢視資料 / 分析 / 即時監控 / 匯出 Excel | ✅ | ✅ | ✅ |\n"
                "| 新增資料 / 批量匯入 | ✅ | ✅ | ❌ |\n"
                "| 修改 / 刪除自己的資料 | ✅ | ✅ | ❌ |\n"
                "| 修改 / 刪除他人的資料 | ✅ | ❌ | ❌ |\n"
                "| 使用者管理 / 日誌 / DB 狀態 / 即時歷史 / 閾值 / 產生器控制 | ✅ | ❌ | ❌ |"
            )

# ---------------- 系統日誌 ----------------
with tabs[1]:
    c1, c2, c3, c4 = st.columns(4)
    levels = c1.multiselect("等級", ["INFO", "WARNING", "ERROR"])
    cats = c2.multiselect("類別", ["request", "auth", "data", "admin", "alert", "event"])
    uname = c3.text_input("使用者")
    kw = c4.text_input("關鍵字（訊息 / 路徑）")
    c5, c6, c7 = st.columns(3)
    log_date = c5.date_input("日期範圍", value=(date.today() - timedelta(days=1), date.today()), key="log_dr")
    lsize = c6.selectbox("每頁", [50, 100, 200], key="log_size")
    lpage = c7.number_input("頁碼", min_value=1, value=1, key="log_page")
    params = {"level": levels, "category": cats, "username": uname, "keyword": kw, "page": lpage, "size": lsize}
    if isinstance(log_date, tuple) and len(log_date) == 2:
        params["start"] = datetime.combine(log_date[0], time.min).isoformat()
        params["end"] = datetime.combine(log_date[1], time.max).isoformat()
    try:
        logs = api.get("/admin/logs", params=api.clean_params(params))
        st.caption(f"共 {logs['total']} 筆")
        if logs["items"]:
            ldf = pd.DataFrame(logs["items"])
            st.dataframe(
                ldf[["created_at", "level", "category", "username", "message", "status_code", "duration_ms", "client_ip"]],
                hide_index=True, use_container_width=True, height=480,
            )
    except api.ApiError as e:
        api.show_error(e)

# ---------------- DB 狀態 ----------------
with tabs[2]:
    if st.button("🔄 重新整理", key="db_refresh"):
        st.rerun()
    try:
        s = api.get("/admin/db-status")
        g = api.get("/realtime/status")
    except api.ApiError as e:
        api.show_error(e)
        st.stop()
    c = st.columns(4)
    c[0].metric("連線", "🟢 正常" if s["connected"] else "🔴 異常")
    c[1].metric("版本", s["server_version"] or "-")
    c[2].metric("延遲", f"{s['latency_ms']} ms" if s["latency_ms"] is not None else "-")
    c[3].metric("方言", s["dialect"])
    st.markdown("**連接池（SQLAlchemy Engine Pool）**")
    p = s["pool"]
    pc = st.columns(4)
    pc[0].metric("Pool size", p["size"] if p["size"] is not None else "-")
    pc[1].metric("Checked out", p["checked_out"] if p["checked_out"] is not None else "-")
    pc[2].metric("Checked in", p["checked_in"] if p["checked_in"] is not None else "-")
    pc[3].metric("Overflow", p["overflow"] if p["overflow"] is not None else "-")
    st.code(p["status"])
    st.markdown("**資料表筆數**")
    counts = pd.DataFrame(list(s["table_counts"].items()), columns=["table", "rows"])
    st.plotly_chart(px.bar(counts, x="table", y="rows", text="rows").update_layout(height=300, margin=dict(t=10)), use_container_width=True)
    st.markdown("**即時產生器 / 批次寫入器**")
    st.json(g)

# ---------------- 即時歷史 ----------------
with tabs[3]:
    c1, c2, c3, c4 = st.columns(4)
    metrics = c1.multiselect("指標", g["metrics"], key="h_metric")
    minutes = c2.selectbox("時間範圍", [5, 15, 60, 360, 1440, 10080], index=2, format_func=lambda m: f"最近 {m} 分鐘")
    only = c3.checkbox("僅顯示異常")
    hpage = c4.number_input("頁碼", min_value=1, value=1, key="h_page")
    hparams = api.clean_params(
        {"metric": metrics, "start": (datetime.now() - timedelta(minutes=minutes)).isoformat(),
         "anomaly_only": only, "page": hpage, "size": 1000}
    )
    try:
        hist = api.get("/realtime/history", params=hparams)
    except api.ApiError as e:
        api.show_error(e)
        hist = None
    if hist:
        st.caption(f"共 {hist['total']} 筆（本頁 {len(hist['items'])} 筆，最多 1000）")
        if hist["items"]:
            hdf = pd.DataFrame(hist["items"])
            hdf["timestamp"] = pd.to_datetime(hdf["timestamp"])
            fig = px.scatter(hdf, x="timestamp", y="value", color="metric", symbol="is_anomaly", facet_row="metric", height=600)
            fig.update_yaxes(matches=None)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(hdf, hide_index=True, use_container_width=True, height=300)
            st.download_button("⬇️ 下載 CSV", hdf.to_csv(index=False).encode("utf-8-sig"), "realtime_history.csv", "text/csv")

# ---------------- 閾值 ----------------
with tabs[4]:
    try:
        th = api.get("/thresholds")
    except api.ApiError as e:
        api.show_error(e)
        th = []
    st.caption("閾值同時套用於即時指標（metric）與資料記錄分類（category）；未設定者使用預設閾值。")
    if th:
        st.dataframe(pd.DataFrame(th), hide_index=True, use_container_width=True)
    with st.form("threshold"):
        t1, t2 = st.columns(2)
        name = t1.text_input("名稱（指標或分類）")
        val = t2.number_input("閾值", value=0.0)
        a, b = st.columns(2)
        save = a.form_submit_button("💾 新增 / 更新", type="primary")
        remove = b.form_submit_button("🗑️ 刪除")
    if save and name:
        try:
            api.put(f"/thresholds/{name}", json={"threshold": val})
            st.success("已儲存")
            st.rerun()
        except api.ApiError as e:
            api.show_error(e)
    if remove and name:
        try:
            api.delete(f"/thresholds/{name}")
            st.success("已刪除")
            st.rerun()
        except api.ApiError as e:
            api.show_error(e)
