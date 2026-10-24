from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from utils import api, auth
from utils.ws import RealtimeStream

st.title("📡 即時監控")

# 每個 Session 一條背景 WebSocket 連線
stream: RealtimeStream | None = st.session_state.get("rt_stream")
if stream is None or stream.token != st.session_state["token"]:
    if stream:
        stream.stop()
    stream = RealtimeStream(st.session_state["token"])
    st.session_state["rt_stream"] = stream
stream.start()

ctrl = st.columns([2, 2, 2, 3])
window = ctrl[0].selectbox("時間視窗", [60, 120, 300, 600], index=1, format_func=lambda s: f"最近 {s} 秒")
refresh = ctrl[1].selectbox("刷新頻率", [1, 2, 5], format_func=lambda s: f"每 {s} 秒")
paused = ctrl[2].toggle("暫停畫面更新", value=False)
if auth.can("admin"):
    with ctrl[3]:
        b1, b2, b3 = st.columns(3)
        try:
            if b1.button("▶ 啟動", use_container_width=True):
                api.post("/realtime/generator/start")
            if b2.button("⏸ 停止", use_container_width=True):
                api.post("/realtime/generator/stop")
            if b3.button("💾 寫入", use_container_width=True, help="立即將緩衝區批次寫入資料庫"):
                st.toast(api.post("/realtime/flush")["message"])
        except api.ApiError as e:
            api.show_error(e)

METRIC_LABELS = {"temperature": "溫度 (°C)", "humidity": "濕度 (%)", "cpu_usage": "CPU 使用率 (%)", "pressure": "氣壓 (hPa)"}


@st.fragment(run_every=refresh)
def live_panel():
    s: RealtimeStream = st.session_state["rt_stream"]
    s.touch()
    status_txt = "🟢 已連線" if s.connected else f"🔴 未連線 {s.last_error or ''}"
    st.caption(f"WebSocket：{status_txt}　|　已接收 {s.received} 次推送　|　{datetime.now():%H:%M:%S}")

    if paused and "rt_frozen" in st.session_state:
        df = st.session_state["rt_frozen"]
    else:
        df = pd.DataFrame(list(s.points))
        st.session_state["rt_frozen"] = df
    if df.empty:
        st.info("等待即時資料中…（若產生器已停止，請由 Admin 啟動）")
        return

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.drop_duplicates(["metric", "timestamp"])
    df = df[df["timestamp"] >= df["timestamp"].max() - timedelta(seconds=window)].sort_values("timestamp")
    metrics = list(dict.fromkeys(df["metric"]))

    # KPI：最新值與變化
    latest = df.groupby("metric").tail(2)
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        rows = latest[latest["metric"] == m]
        cur = rows.iloc[-1]
        delta = cur["value"] - rows.iloc[0]["value"] if len(rows) > 1 else 0
        col.metric(
            METRIC_LABELS.get(m, m) + (" 🚨" if cur["is_anomaly"] else ""),
            f"{cur['value']:.2f}",
            f"{delta:+.2f}",
            delta_color="inverse",
            help=f"閾值 {cur['threshold']}",
        )

    # 折線圖：每個指標一個子圖，閾值虛線、異常點紅色標記
    rows_n = (len(metrics) + 1) // 2
    fig = make_subplots(rows=rows_n, cols=2, subplot_titles=[METRIC_LABELS.get(m, m) for m in metrics], vertical_spacing=0.12)
    for i, m in enumerate(metrics):
        r, c = i // 2 + 1, i % 2 + 1
        d = df[df["metric"] == m]
        fig.add_trace(go.Scatter(x=d["timestamp"], y=d["value"], mode="lines", name=m, line=dict(width=2)), row=r, col=c)
        fig.add_trace(
            go.Scatter(x=d["timestamp"], y=d["threshold"], mode="lines", name=f"{m} 閾值", line=dict(dash="dash", color="gray", width=1)),
            row=r, col=c,
        )
        a = d[d["is_anomaly"]]
        if not a.empty:
            fig.add_trace(
                go.Scatter(x=a["timestamp"], y=a["value"], mode="markers", name=f"{m} 異常", marker=dict(color="red", size=9, symbol="x")),
                row=r, col=c,
            )
    fig.update_layout(height=280 * rows_n, showlegend=False, margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True, key="rt_line")

    left, right = st.columns(2)
    with left:
        st.markdown("**最新值 / 閾值（%）**")
        last = df.groupby("metric").tail(1).copy()
        last["ratio"] = (last["value"] / last["threshold"] * 100).round(1)
        bar = go.Figure(
            go.Bar(
                x=last["metric"], y=last["ratio"], text=last["ratio"].astype(str) + "%",
                marker_color=["#dc2626" if x else "#2563eb" for x in last["is_anomaly"]],
            )
        )
        bar.add_hline(y=100, line_dash="dash", line_color="red")
        bar.update_layout(height=300, margin=dict(t=10, b=10), yaxis_title="%")
        st.plotly_chart(bar, use_container_width=True, key="rt_bar")
    with right:
        st.markdown("**視窗內異常次數**")
        counts = df[df["is_anomaly"]].groupby("metric").size().reindex(metrics, fill_value=0)
        bar2 = go.Figure(go.Bar(x=counts.index, y=counts.values, marker_color="#f97316", text=counts.values))
        bar2.update_layout(height=300, margin=dict(t=10, b=10))
        st.plotly_chart(bar2, use_container_width=True, key="rt_bar2")

    st.markdown("**🚨 最近告警**")
    alerts = list(s.alerts)[-20:][::-1]
    seen = st.session_state.setdefault("rt_seen_alerts", set())
    for a in alerts[:5]:
        key = (a["metric"], a["timestamp"])
        if key not in seen:
            seen.add(key)
            st.toast(f"{a['metric']} = {a['value']} 超過閾值 {a['threshold']}", icon="🚨")
    if alerts:
        st.dataframe(pd.DataFrame(alerts), hide_index=True, use_container_width=True, height=220)
    else:
        st.caption("目前沒有告警")


live_panel()
