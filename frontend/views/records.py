from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from utils import api, auth

st.title("📋 資料管理")
user = auth.current_user()
can_write = auth.can("admin", "user")

SAMPLE_CSV = (
    "title,value,category,timestamp,description\n"
    "Sensor A,23.5,temperature,2026-10-01T08:00:00,morning reading\n"
    "Order #1001,1250,sales,2026-10-01T09:30:00,online order\n"
)


def can_modify(rec: dict) -> bool:
    return auth.can("admin") or (auth.can("user") and rec["owner_id"] == user["id"])


try:
    categories = api.get("/records/categories")
except api.ApiError as e:
    api.show_error(e)
    st.stop()

tabs = st.tabs(["🔎 查詢", "➕ 新增", "✏️ 編輯 / 刪除", "📥 批量匯入"])

# ---------------- 查詢 ----------------
with tabs[0]:
    with st.expander("篩選條件", expanded=True):
        f1, f2, f3 = st.columns(3)
        sel_cats = f1.multiselect("分類", categories)
        keyword = f2.text_input("標題關鍵字")
        anomaly = f3.selectbox("異常", ["全部", "僅異常", "僅正常"])
        f4, f5, f6, f7 = st.columns(4)
        use_date = f4.checkbox("限定日期範圍")
        dr = f5.date_input("日期範圍", value=(date.today() - timedelta(days=30), date.today()), disabled=not use_date)
        min_v = f6.number_input("最小值", value=None, placeholder="不限")
        max_v = f7.number_input("最大值", value=None, placeholder="不限")
        mine = st.checkbox("只看我建立的", disabled=not can_write)

    s1, s2, s3, s4 = st.columns(4)
    sort_by = s1.selectbox("排序欄位", ["timestamp", "value", "title", "category", "id", "created_at"])
    order = s2.selectbox("排序方向", ["desc", "asc"], format_func=lambda x: "遞減" if x == "desc" else "遞增")
    size = s3.selectbox("每頁筆數", [10, 20, 50, 100], index=1)
    page = s4.number_input("頁碼", min_value=1, value=1, step=1)

    params = {
        "category": sel_cats,
        "keyword": keyword,
        "min_value": min_v,
        "max_value": max_v,
        "sort_by": sort_by,
        "order": order,
        "size": size,
        "page": page,
        "owner_id": user["id"] if mine else None,
        "is_anomaly": {"僅異常": True, "僅正常": False}.get(anomaly),
    }
    if use_date and isinstance(dr, tuple) and len(dr) == 2:
        params["start"] = datetime.combine(dr[0], time.min).isoformat()
        params["end"] = datetime.combine(dr[1], time.max).isoformat()
    try:
        result = api.get("/records", params=api.clean_params(params))
    except api.ApiError as e:
        api.show_error(e)
        st.stop()

    st.caption(f"共 {result['total']} 筆，第 {result['page']} / {max(result['pages'], 1)} 頁")
    if result["items"]:
        df = pd.DataFrame(result["items"])
        df = df[["id", "title", "value", "category", "timestamp", "is_anomaly", "owner_username", "description", "updated_at"]]
        st.dataframe(
            df.style.apply(lambda r: ["background-color: #fee2e2" if r["is_anomaly"] else "" for _ in r], axis=1),
            hide_index=True,
            use_container_width=True,
            column_config={"is_anomaly": st.column_config.CheckboxColumn("異常"), "value": st.column_config.NumberColumn("數值", format="%.2f")},
        )
    else:
        st.info("沒有符合條件的資料")

# ---------------- 新增 ----------------
with tabs[1]:
    if not can_write:
        st.warning("Viewer 角色僅能檢視資料。")
    else:
        with st.form("create", clear_on_submit=True):
            c1, c2 = st.columns(2)
            title = c1.text_input("標題 *")
            value = c2.number_input("數值 *", value=0.0, format="%.4f")
            c3, c4 = st.columns(2)
            cat_choice = c3.selectbox("分類 *", categories + ["（新分類）"]) if categories else "（新分類）"
            new_cat = c4.text_input("新分類名稱", disabled=cat_choice != "（新分類）")
            c5, c6 = st.columns(2)
            d = c5.date_input("日期", value=date.today())
            t = c6.time_input("時間", value=datetime.now().time().replace(microsecond=0))
            desc = st.text_area("描述")
            if st.form_submit_button("新增", type="primary"):
                category = new_cat if cat_choice == "（新分類）" else cat_choice
                try:
                    rec = api.post(
                        "/records",
                        json={"title": title, "value": value, "category": category,
                              "timestamp": datetime.combine(d, t).isoformat(), "description": desc or None},
                    )
                    st.success(f"已新增 #{rec['id']}" + ("（⚠️ 超過閾值，已標記為異常）" if rec["is_anomaly"] else ""))
                except api.ApiError as e:
                    api.show_error(e)

# ---------------- 編輯 / 刪除 ----------------
with tabs[2]:
    rid = st.number_input("資料 ID", min_value=1, step=1, value=None, placeholder="輸入要編輯的資料 ID")
    if rid:
        try:
            rec = api.get(f"/records/{int(rid)}")
        except api.ApiError as e:
            api.show_error(e)
            rec = None
        if rec:
            editable = can_modify(rec)
            if not editable:
                st.info(f"此筆資料由 **{rec['owner_username']}** 建立，僅建立者或 Admin 可以修改。")
            ts = datetime.fromisoformat(rec["timestamp"])
            with st.form("edit"):
                c1, c2 = st.columns(2)
                title = c1.text_input("標題", value=rec["title"], disabled=not editable)
                value = c2.number_input("數值", value=float(rec["value"]), format="%.4f", disabled=not editable)
                c3, c4, c5 = st.columns(3)
                category = c3.text_input("分類", value=rec["category"], disabled=not editable)
                d = c4.date_input("日期", value=ts.date(), disabled=not editable)
                t = c5.time_input("時間", value=ts.time(), disabled=not editable)
                desc = st.text_area("描述", value=rec.get("description") or "", disabled=not editable)
                b1, b2 = st.columns(2)
                save = b1.form_submit_button("💾 儲存", type="primary", disabled=not editable)
                remove = b2.form_submit_button("🗑️ 刪除", disabled=not editable)
            if save:
                try:
                    api.put(
                        f"/records/{rec['id']}",
                        json={"title": title, "value": value, "category": category,
                              "timestamp": datetime.combine(d, t).isoformat(), "description": desc or None},
                    )
                    st.success("已更新")
                except api.ApiError as e:
                    api.show_error(e)
            if remove:
                try:
                    api.delete(f"/records/{rec['id']}")
                    st.success(f"已刪除 #{rec['id']}")
                except api.ApiError as e:
                    api.show_error(e)

# ---------------- 匯入 ----------------
with tabs[3]:
    if not can_write:
        st.warning("Viewer 角色無法匯入資料。")
    else:
        st.markdown(
            "支援 **CSV**（欄位：`title,value,category,timestamp,description`，前三欄必填）"
            "或 **JSON**（陣列或 `{\"records\": [...]}`）。最大 5MB。"
        )
        st.download_button("下載 CSV 範本", SAMPLE_CSV, "records_template.csv", "text/csv")
        up = st.file_uploader("選擇檔案", type=["csv", "json"])
        if up and st.button("開始匯入", type="primary"):
            try:
                res = api.post("/records/import", files={"file": (up.name, up.getvalue(), up.type)})
                c = st.columns(4)
                c[0].metric("總筆數", res["total"])
                c[1].metric("成功", res["imported"])
                c[2].metric("失敗", res["failed"])
                c[3].metric("異常", res["anomalies"])
                if res["errors"]:
                    st.dataframe(pd.DataFrame(res["errors"]), hide_index=True, use_container_width=True)
            except api.ApiError as e:
                api.show_error(e)
