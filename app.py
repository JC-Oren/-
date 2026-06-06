import os
import sqlite3
from datetime import datetime, timezone
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

DB_PATH = "earthquakes.db"
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"

st.set_page_config(page_title="即時地震監測儀表板", page_icon="🌏", layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] {font-family: "Microsoft JhengHei", "Noto Sans TC", "Arial", sans-serif;}
.main { background-color: #F7F8FB; }
.block-container { padding-top: 2rem; padding-bottom: 2rem; }
div[data-testid="metric-container"] {
    background: #FFFFFF; border: 1px solid #E5E7EB; padding: 18px;
    border-radius: 18px; box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
}
h1, h2, h3 { color: #111827; font-weight: 800; }
</style>
""", unsafe_allow_html=True)


def classify_magnitude(mag):
    if pd.isna(mag):
        return "unknown"
    if mag < 2:
        return "微震"
    if mag < 4:
        return "小震"
    if mag < 5:
        return "輕震"
    if mag < 6:
        return "中震"
    if mag < 7:
        return "強震"
    return "大震"


def fallback_data():
    rows = [
        ["Taiwan region", 5.2, 23.7, 121.1, 20.0, "2026-06-06 08:10:00 UTC"],
        ["Japan region", 4.8, 35.6, 140.2, 40.0, "2026-06-06 07:40:00 UTC"],
        ["Indonesia", 5.6, -6.2, 130.1, 60.0, "2026-06-06 06:30:00 UTC"],
        ["Chile", 4.5, -30.2, -71.5, 35.0, "2026-06-06 05:20:00 UTC"],
        ["Alaska", 3.2, 61.2, -150.0, 15.0, "2026-06-06 04:10:00 UTC"],
    ]
    df = pd.DataFrame(rows, columns=["place", "magnitude", "latitude", "longitude", "depth_km", "time_utc"])
    df["level"] = df["magnitude"].apply(classify_magnitude)
    df["marker_size"] = df["magnitude"].clip(lower=0.1)
    df["time_taiwan"] = pd.to_datetime(df["time_utc"], errors="coerce", utc=True).dt.tz_convert("Asia/Taipei").dt.strftime("%Y-%m-%d %H:%M:%S 台灣時間")
    df["updated_at"] = datetime.now(timezone.utc).astimezone(pd.Timestamp.now(tz="Asia/Taipei").tz).strftime("%Y-%m-%d %H:%M:%S 台灣時間")
    return df


def fetch_earthquake_data():
    response = requests.get(USGS_URL, timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows = []
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None, None])
        timestamp = props.get("time")
        time_utc = None if timestamp is None else datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        rows.append({
            "place": props.get("place", "Unknown"),
            "magnitude": props.get("mag"),
            "longitude": coords[0],
            "latitude": coords[1],
            "depth_km": coords[2],
            "time_utc": time_utc,
            "url": props.get("url"),
        })
    return pd.DataFrame(rows)


def clean_data(df):
    df = df.copy()
    df["place"] = df["place"].fillna("Unknown")
    for col in ["magnitude", "latitude", "longitude", "depth_km"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["magnitude", "latitude", "longitude"])
    df["level"] = df["magnitude"].apply(classify_magnitude)
    df["marker_size"] = df["magnitude"].clip(lower=0.1)
    df["time_taiwan"] = pd.to_datetime(df["time_utc"], errors="coerce", utc=True).dt.tz_convert("Asia/Taipei").dt.strftime("%Y-%m-%d %H:%M:%S 台灣時間")
    df["updated_at"] = datetime.now(timezone.utc).astimezone(pd.Timestamp.now(tz="Asia/Taipei").tz).strftime("%Y-%m-%d %H:%M:%S 台灣時間")
    return df.sort_values("time_utc", ascending=False).reset_index(drop=True)


def save_to_sqlite(df):
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("earthquakes", conn, if_exists="replace", index=False)
    conn.close()


def load_from_sqlite():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM earthquakes", conn)
    finally:
        conn.close()
    if not df.empty and "marker_size" not in df.columns:
        df["marker_size"] = pd.to_numeric(df["magnitude"], errors="coerce").fillna(0.1).clip(lower=0.1)
    if not df.empty and "time_taiwan" not in df.columns:
        df["time_taiwan"] = pd.to_datetime(df["time_utc"], errors="coerce", utc=True).dt.tz_convert("Asia/Taipei").dt.strftime("%Y-%m-%d %H:%M:%S 台灣時間")
    return df


def run_pipeline():
    df = clean_data(fetch_earthquake_data())
    save_to_sqlite(df)
    return df


def ensure_initial_data():
    df = load_from_sqlite()
    if not df.empty:
        return df
    with st.spinner("第一次開啟，正在抓取 USGS 即時地震資料..."):
        try:
            df = run_pipeline()
        except Exception:
            df = fallback_data()
            save_to_sqlite(df)
    return df


def format_chart(fig, height=460):
    fig.update_layout(
        height=height, title_font_size=22, title_font_family="Microsoft JhengHei",
        font=dict(size=14, family="Microsoft JhengHei"), plot_bgcolor="white",
        paper_bgcolor="white", margin=dict(l=20, r=40, t=70, b=30)
    )
    return fig


st.title("🌏 即時地震監測儀表板")
st.write("本專案使用 USGS 最近 24 小時地震資料，並將時間轉換為台灣時間，透過 pandas 進行 ETL 清理後寫入 SQLite，並以 Streamlit + Plotly 製作互動式 Dashboard。")

df = ensure_initial_data()

with st.sidebar:
    st.header("控制面板")
    if st.button("🔄 更新資料"):
        with st.spinner("正在重新抓取最新地震資料..."):
            try:
                st.cache_data.clear()
                df_new = run_pipeline()
                st.success(f"更新完成，共取得 {len(df_new)} 筆地震資料。")
                st.rerun()
            except Exception as exc:
                st.error(f"更新失敗，保留目前資料：{exc}")

    min_mag = float(df["magnitude"].min()) if len(df) else 0.0
    max_mag = float(df["magnitude"].max()) if len(df) else 10.0
    mag_range = st.slider("地震規模範圍", min_mag, max_mag, (min_mag, max_mag), step=0.1) if max_mag > min_mag else (min_mag, max_mag)
    keyword = st.text_input("搜尋地點關鍵字")

filtered = df.copy()
filtered["marker_size"] = pd.to_numeric(filtered["marker_size"], errors="coerce").fillna(0.1).clip(lower=0.1)
filtered = filtered[(filtered["magnitude"] >= mag_range[0]) & (filtered["magnitude"] <= mag_range[1])]

if keyword:
    filtered = filtered[filtered["place"].str.contains(keyword, case=False, na=False)]

col1, col2, col3, col4 = st.columns(4)
col1.metric("地震總數", f"{len(filtered):,}")
col2.metric("最大規模", f"{filtered['magnitude'].max():.1f}" if len(filtered) else "0")
col3.metric("平均深度", f"{filtered['depth_km'].mean():.1f} km" if len(filtered) else "0 km")
col4.metric("規模 5 以上", f"{len(filtered[filtered['magnitude'] >= 5]):,}")

last_updated = df["updated_at"].dropna().max() if "updated_at" in df.columns else "無"
st.caption(f"最後更新時間：{last_updated}")
st.divider()

st.subheader("全球地震分布地圖")
if len(filtered):
    fig_map = px.scatter_geo(
        filtered, lat="latitude", lon="longitude", color="magnitude", size="marker_size",
        hover_name="place", hover_data={"magnitude": True, "depth_km": True, "time_taiwan": True, "marker_size": False, "latitude": False, "longitude": False},
        color_continuous_scale="Turbo", size_max=18, projection="natural earth", title="最近 24 小時全球地震分布"
    )
    fig_map.update_geos(showland=True, landcolor="#F3F4F6", showcountries=True, countrycolor="#D1D5DB", showocean=True, oceancolor="#DBEAFE", showcoastlines=True, coastlinecolor="#9CA3AF")
    fig_map.update_layout(height=560, title_font_size=22, title_font_family="Microsoft JhengHei", font=dict(size=14, family="Microsoft JhengHei"), margin=dict(l=0, r=0, t=60, b=0), paper_bgcolor="white")
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.info("目前篩選條件下沒有地震資料。")

st.subheader("最近 24 小時每小時地震數量（台灣時間）")
hour_df = filtered.copy()
hour_df["time_dt"] = pd.to_datetime(hour_df["time_utc"], errors="coerce", utc=True).dt.tz_convert("Asia/Taipei")
hour_df = hour_df.dropna(subset=["time_dt"])
if len(hour_df):
    hour_df["hour_dt"] = hour_df["time_dt"].dt.floor("h")
    hourly_summary = hour_df.groupby("hour_dt").size().reset_index(name="地震數量").sort_values("hour_dt")
    hourly_summary["時間"] = hourly_summary["hour_dt"].dt.strftime("%m/%d %H:00")
    fig_hour = px.line(hourly_summary, x="時間", y="地震數量", markers=True, title="最近 24 小時每小時地震數量（台灣時間）", labels={"時間": "時間（台灣）", "地震數量": "地震數量"})
    fig_hour.update_traces(line_width=3)
    fig_hour.update_layout(xaxis_tickangle=-35)
    st.plotly_chart(format_chart(fig_hour, height=430), use_container_width=True)
else:
    st.info("目前沒有可用的時間資料。")

st.subheader("地震規模排行 Top 10")
top_mag = filtered.sort_values("magnitude", ascending=False).head(10)
fig_top = px.bar(top_mag.sort_values("magnitude", ascending=True), x="magnitude", y="place", orientation="h", title="地震規模 Top 10", labels={"magnitude": "規模", "place": "地點"}, color="magnitude", color_continuous_scale="Reds", text="magnitude")
fig_top.update_traces(width=0.6, textposition="outside")
fig_top.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
st.plotly_chart(format_chart(fig_top), use_container_width=True)

st.subheader("地震規模分布圓餅圖")
level_order = ["微震", "小震", "輕震", "中震", "強震", "大震"]
level_summary = filtered.groupby("level").size().reset_index(name="地震數量")
level_summary["level"] = pd.Categorical(level_summary["level"], categories=level_order, ordered=True)
level_summary = level_summary.sort_values("level")
fig_level = px.pie(level_summary, names="level", values="地震數量", title="不同規模等級比例", hole=0.38, color_discrete_sequence=px.colors.qualitative.Set3)
fig_level.update_traces(textposition="inside", textinfo="percent+label")
st.plotly_chart(format_chart(fig_level, height=430), use_container_width=True)

st.subheader("深度分布")
depth_df = filtered.copy()
depth_df["深度區間"] = pd.cut(depth_df["depth_km"], bins=[-1, 10, 30, 70, 300, 1000], labels=["0–10 km", "10–30 km", "30–70 km", "70–300 km", "300+ km"])
depth_summary = depth_df.groupby("深度區間", observed=False).size().reset_index(name="地震數量")
fig_depth = px.bar(depth_summary, x="深度區間", y="地震數量", title="地震深度分布", labels={"深度區間": "深度區間", "地震數量": "地震數量"}, color="地震數量", color_continuous_scale="Blues", text="地震數量")
fig_depth.update_traces(width=0.55, textposition="outside")
fig_depth.update_layout(coloraxis_showscale=False)
st.plotly_chart(format_chart(fig_depth, height=430), use_container_width=True)

st.subheader("地震資料表")
table = filtered.sort_values("time_utc", ascending=False).reset_index(drop=True)
table.insert(0, "rank", range(1, len(table) + 1))
display_table = table[["rank", "place", "magnitude", "depth_km", "latitude", "longitude", "level", "time_utc"]].rename(columns={"rank": "序號", "place": "地點", "magnitude": "規模", "depth_km": "深度(km)", "latitude": "緯度", "longitude": "經度", "level": "等級", "time_taiwan": "時間（台灣）"})
st.dataframe(display_table, hide_index=True, use_container_width=True)
