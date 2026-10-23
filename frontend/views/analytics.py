from datetime import date, datetime, time, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import api

st.title("📊 資料分析")

try:
    categories = api.get("/records/categories")
except api.ApiError as e:
    api.show_error(e)
    st.stop()

tab_rec, tab_rt = st.tabs(["資料記錄分析", "即時資料分析"])

with tab_rec:
    f1, f2, f3 = st.columns([2, 3, 1])
    dr = f1.date_input("時間範圍", value=(date.today() - timedelta(days=90), date.today()))
    sel = f2.multiselect("分類（不選＝全部）", categories)
    interval = f3.selectbox("趨勢粒度", ["day", "hour", "month"], format_func={"day": "日", "hour": "小時", "month": "月"}.get)

    params = {"category": sel}
    if isinstance(dr, tuple) and len(dr) == 2:
        params["start"] = datetime.combine(dr[0], time.min).isoformat()
        params["end"] = datetime.combine(dr[1], time.max).isoformat()
    params = api.clean_params(params)

    try:
        summary = api.get("/analytics/summary", params=params)
        cats = api.get("/analytics/by-category", params=params)
        trend = api.get("/analytics/trend", params={**params, "interval": interval, "by_category": True})
    except api.ApiError as e:
        api.show_error(e)
        st.stop()

    c = st.columns(6)
    fmt = lambda v: "-" if v is None else f"{v:,.2f}"  # noqa: E731
    c[0].metric("筆數", f"{summary['count']:,}")
    c[1].metric("總計", fmt(summary["total"]))
    c[2].metric("平均", fmt(summary["average"]))
    c[3].metric("最大", fmt(summary["maximum"]))
    c[4].metric("最小", fmt(summary["minimum"]))
    c[5].metric("異常", summary["anomalies"])

    if summary["count"] == 0:
        st.info("此範圍內沒有資料")
    else:
        left, right = st.columns(2)
        cdf = pd.DataFrame(cats)
        with left:
            st.subheader("分類聚合")
            metric = st.radio("指標", ["total", "average", "count", "maximum", "minimum"], horizontal=True,
                              format_func={"total": "總計", "average": "平均", "count": "筆數", "maximum": "最大", "minimum": "最小"}.get)
            fig = px.bar(cdf, x="category", y=metric, color="category", text_auto=".2s")
            fig.update_layout(height=360, showlegend=False, margin=dict(t=10))
            st.plotly_chart(fig, use_container_width=True)
        with right:
            st.subheader("分類占比（筆數）")
            fig = px.pie(cdf, names="category", values="count", hole=0.45)
            fig.update_layout(height=400, margin=dict(t=10))
            st.plotly_chart(fig, use_container_width=True)

        st.dataframe(cdf, hide_index=True, use_container_width=True)

        st.subheader("趨勢")
        if trend:
            tdf = pd.DataFrame(trend)
            y = st.radio("趨勢指標", ["average", "count", "maximum", "minimum"], horizontal=True, key="trend_y",
                         format_func={"average": "平均", "count": "筆數", "maximum": "最大", "minimum": "最小"}.get)
            fig = px.line(tdf, x="bucket", y=y, color="category", markers=True)
            fig.update_layout(height=380, margin=dict(t=10), xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    if st.button("📥 產生 Excel 報表", type="primary"):
        try:
            resp = api.get("/analytics/export", params={**params, "interval": interval}, raw=True)
            st.session_state["xlsx"] = resp.content
        except api.ApiError as e:
            api.show_error(e)
    if st.session_state.get("xlsx"):
        st.download_button(
            "⬇️ 下載 Excel",
            st.session_state["xlsx"],
            file_name=f"analytics_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

with tab_rt:
    minutes = st.select_slider("時間範圍", options=[5, 15, 30, 60, 180, 720, 1440], value=30, format_func=lambda m: f"最近 {m} 分鐘")
    start = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    try:
        rs = api.get("/analytics/realtime/summary", params={"start": start})
        rt = api.get("/analytics/realtime/trend", params={"start": start, "interval": "minute"})
    except api.ApiError as e:
        api.show_error(e)
        st.stop()
    if not rs:
        st.info("此範圍內尚無已寫入資料庫的即時資料")
    else:
        st.dataframe(pd.DataFrame(rs), hide_index=True, use_container_width=True)
        tdf = pd.DataFrame(rt)
        fig = px.line(tdf, x="bucket", y="average", color="metric", facet_col="metric", facet_col_wrap=2, markers=True)
        fig.update_yaxes(matches=None)
        fig.update_layout(height=520, showlegend=False, margin=dict(t=30))
        st.plotly_chart(fig, use_container_width=True)
