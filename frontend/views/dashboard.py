import pandas as pd
import plotly.express as px
import streamlit as st

from utils import api, auth

st.title("🏠 儀表板")
user = auth.current_user()

try:
    summary = api.get("/analytics/summary")
    status = api.get("/realtime/status")
    cats = api.get("/analytics/by-category")
    recent = api.get("/records", params={"size": 8, "sort_by": "created_at", "order": "desc"})
except api.ApiError as e:
    api.show_error(e)
    st.stop()

c = st.columns(5)
c[0].metric("資料筆數", f"{summary['count']:,}")
c[1].metric("平均值", f"{summary['average']:.2f}" if summary["average"] is not None else "-")
c[2].metric("最大值", summary["maximum"] if summary["maximum"] is not None else "-")
c[3].metric("異常筆數", summary["anomalies"])
c[4].metric("WebSocket 連線", status["websocket_clients"])

s = st.columns(4)
s[0].metric("產生器", "🟢 運行中" if status["running"] else "🔴 已停止")
s[1].metric("已產生點數", f"{status['total_generated']:,}")
s[2].metric("已批次寫入", f"{status['total_flushed']:,}")
s[3].metric("緩衝區", f"{status['buffer_size']} / {status['batch_max_size']}")
if status["last_flush_at"]:
    st.caption(f"最後批次寫入：{status['last_flush_at']}（觸發原因：{status['last_flush_reason']}）")

left, right = st.columns(2)
with left:
    st.subheader("分類筆數")
    if cats:
        df = pd.DataFrame(cats)
        fig = px.bar(df, x="category", y="count", color="anomalies", color_continuous_scale="Reds", text="count")
        fig.update_layout(height=340, margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("尚無資料")
with right:
    st.subheader("最新資料")
    if recent["items"]:
        df = pd.DataFrame(recent["items"])[["id", "title", "value", "category", "timestamp", "is_anomaly", "owner_username"]]
        st.dataframe(df, hide_index=True, use_container_width=True, height=340)
    else:
        st.info("尚無資料")
