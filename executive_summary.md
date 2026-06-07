# 即時地震監測儀表板 Executive Summary

本專案使用 USGS Earthquake GeoJSON Feed 作為即時資料來源，透過 requests 抓取最近 24 小時全球地震事件，使用 pandas 進行資料清理、時間轉換、規模分類與欄位整理，並將處理後資料寫入 SQLite。前端以 Streamlit 建立互動式 Dashboard，並使用 Plotly 呈現全球地震地圖、最近 24 小時每小時地震數量、地震規模排行、規模分布圓餅圖、深度分布圖與資料表。使用者可按「更新資料」重新抓取最新地震資料，因此能清楚展示資料更新機制。
