import streamlit as st
import pandas as pd
from google.cloud import bigquery
import plotly.express as px
import os
from dotenv import load_dotenv

# 載入環境變數 (確保能讀取到 GCP 權限)
load_dotenv()

# 設定網頁標題與寬度
st.set_page_config(page_title="Q-Silicon 戰情室", page_icon="🛡️", layout="wide")

st.title("🛡️ Q-Silicon 終極投資戰情室")
st.caption("自動化情報聚合 ｜ 巨鯨資金流向 ｜ AI 算力定價")

# --- 區塊 1：核心市場模式 (Market Regime) ---
st.subheader("🔴 當前市場模式 (Market Regime)")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="市場模式", value="Risk OFF", delta="- 高度警戒", delta_color="inverse")
with col2:
    st.metric(label="ICE DXY (美元指數)", value="97.74", delta="-0.04%")
with col3:
    st.metric(label="NVIDIA B200 租賃價", value="$3.40 / hr", delta="算力通縮")
with col4:
    st.metric(label="BTC ETF 資金流", value="-$38億", delta="連續五週流出", delta_color="inverse")

st.divider()

# --- 區塊 2：BigQuery 巨鯨資金流向雷達 ---
st.subheader("🐋 鏈上巨鯨資金流向 (BigQuery 實時連線)")

@st.cache_data(ttl=600) # 快取 10 分鐘，避免頻繁查詢 BigQuery
def load_whale_data():
    try:
        # 連線到 GCP BigQuery
        client = bigquery.Client(project="my-investment-ai-agent")

        # 查詢過去 7 天的巨鯨轉帳紀錄
        query = """
            SELECT timestamp, amount
            FROM `my-investment-ai-agent.market_data.btc_whale_transactions`
            ORDER BY timestamp DESC
            LIMIT 100
        """
        df = client.query(query).to_dataframe()
        return df
    except Exception as e:
        st.error(f"BigQuery 連線或查詢失敗: {e}")
        return pd.DataFrame()

df_whales = load_whale_data()

if df_whales.empty:
    st.info("🟢 目前 BigQuery 資料庫中尚無巨鯨轉帳紀錄 (或者剛建表尚無數據流入)。")
else:
    # 繪製 Plotly 互動式圖表
    fig = px.bar(
        df_whales,
        x='timestamp',
        y='amount',
        title="BTC 巨鯨大額轉帳歷史 (單位: BTC)",
        labels={'timestamp': '時間', 'amount': '轉帳數量 (BTC)'},
        color='amount',
        color_continuous_scale=px.colors.sequential.Agsunset
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("查看原始數據"):
        st.dataframe(df_whales)

st.divider()

# --- 區塊 3：Agent 戰略觀點 (預留擴充) ---
st.subheader("🧠 核心 Agent 戰略點評")
tab1, tab2 = st.tabs(["🛸 幣圈暗網情報 (Grok)", "🤖 AI 前沿與算力 (GPT)"])

with tab1:
    st.warning("⚠️ **Grok 警告**：Jane Street 訴訟案正在發酵，市場深陷 10am dump 陰謀論。散戶 FUD 嚴重，請勿盲目抄底。")
    st.write("🔥 **熱門推文擷取**：'Reddit user claims DOJ has started internal investigation into Jane Street...'")

with tab2:
    st.info("💡 **GPT 洞察**：算力從軍備競賽轉向資本效率。OpenAI 1100億美元超級融資鎖死算力霸權，中小型開源模型生存空間遭壓縮。")
    st.write("🔥 **熱門推文擷取**：'Sam Altman spills tea on Anthropic's Pentagon drama...'")

st.caption("Powered by CrewAI & Google Cloud BigQuery")
