import streamlit as st
import pandas as pd
from google.cloud import bigquery
import plotly.express as px
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Q-Silicon 戰情室", page_icon="🛡️", layout="wide")

st.title("🛡️ Q-Silicon 終極投資戰情室")
st.caption("自動化情報聚合 ｜ 巨鯨資金流向 ｜ AI 算力定價")

PROJECT_ID = "my-investment-ai-agent"


# ── 讀取每日指標（動態 KPI 來源）─────────────────────────────────────
@st.cache_data(ttl=300)
def load_daily_metrics() -> dict:
    """從 BigQuery daily_metrics 取最新一筆紀錄，回傳 dict，失敗時全為 None。"""
    try:
        client = bigquery.Client(project=PROJECT_ID)
        query = f"""
            SELECT timestamp, dxy, etf_flow_millions, avg_risk_score,
                   gpu_b200_price, grok_summary, gpt_summary
            FROM `{PROJECT_ID}.market_data.daily_metrics`
            ORDER BY timestamp DESC
            LIMIT 1
        """
        df = client.query(query).to_dataframe()
        if df.empty:
            return {}
        row = df.iloc[0]
        return {
            "timestamp":        row.get("timestamp"),
            "dxy":              row.get("dxy"),
            "etf_flow":         row.get("etf_flow_millions"),
            "avg_risk_score":   row.get("avg_risk_score"),
            "gpu_b200_price":   row.get("gpu_b200_price"),
            "grok_summary":     row.get("grok_summary"),
            "gpt_summary":      row.get("gpt_summary"),
        }
    except Exception as e:
        st.warning(f"⚠️ 無法讀取 daily_metrics：{e}")
        return {}


# ── 讀取巨鯨數據 ──────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_whale_data() -> pd.DataFrame:
    try:
        client = bigquery.Client(project=PROJECT_ID)
        query = f"""
            SELECT timestamp, amount
            FROM `{PROJECT_ID}.market_data.btc_whale_transactions`
            ORDER BY timestamp DESC
            LIMIT 100
        """
        return client.query(query).to_dataframe()
    except Exception as e:
        st.error(f"BigQuery 連線或查詢失敗: {e}")
        return pd.DataFrame()


# ════════════════════════════════════════════════════════════════════
# 區塊 1：核心市場模式 KPI（動態讀取）
# ════════════════════════════════════════════════════════════════════
metrics = load_daily_metrics()

avg_risk   = metrics.get("avg_risk_score")
dxy_val    = metrics.get("dxy")
etf_val    = metrics.get("etf_flow")

# 根據平均風險分數判斷市場模式
if avg_risk is not None:
    if avg_risk >= 3.5:
        regime_label = "🔴 Risk OFF"
        regime_delta = "高度警戒"
        regime_color = "inverse"
    else:
        regime_label = "🟢 Risk ON"
        regime_delta = "尋找機會"
        regime_color = "normal"
else:
    regime_label = "N/A"
    regime_delta = "尚無數據"
    regime_color = "off"

b200_val   = metrics.get("gpu_b200_price")

dxy_display = f"{dxy_val:.2f}" if dxy_val is not None else "N/A"
b200_display = f"${b200_val:.2f} / hr" if b200_val is not None else "N/A"
etf_display = (
    f"-${abs(etf_val):.0f}億" if etf_val is not None and etf_val < 0
    else f"+${etf_val:.0f}億" if etf_val is not None
    else "N/A"
)
etf_color = "inverse" if (etf_val is not None and etf_val < 0) else "normal"

st.subheader("市場模式總覽")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="當前市場模式", value=regime_label, delta=regime_delta, delta_color=regime_color)
with col2:
    st.metric(label="ICE DXY（美元指數）", value=dxy_display)
with col3:
    st.metric(label="NVIDIA B200 租賃價", value=b200_display)
with col4:
    st.metric(label="BTC ETF 資金流", value=etf_display, delta_color=etf_color)

# 最後更新時間
if metrics.get("timestamp"):
    st.caption(f"數據更新時間：{metrics['timestamp']}")

st.divider()

# ════════════════════════════════════════════════════════════════════
# 區塊 2：每日風險趨勢折線圖
# ════════════════════════════════════════════════════════════════════
st.subheader("📈 每日平均風險分數趨勢 (BigQuery)")

@st.cache_data(ttl=600)
def load_risk_trend() -> pd.DataFrame:
    try:
        client = bigquery.Client(project=PROJECT_ID)
        query = f"""
            SELECT timestamp, avg_risk_score, dxy, etf_flow_millions
            FROM `{PROJECT_ID}.market_data.daily_metrics`
            ORDER BY timestamp ASC
            LIMIT 30
        """
        return client.query(query).to_dataframe()
    except Exception:
        return pd.DataFrame()

df_trend = load_risk_trend()

if df_trend.empty:
    st.info("尚無歷史指標數據，等待第一次戰報寫入後自動顯示。")
else:
    tab_risk, tab_dxy, tab_etf = st.tabs(["⚠️ 平均風險分數", "💵 ICE DXY", "💸 ETF 資金流"])
    with tab_risk:
        fig_risk = px.line(
            df_trend, x="timestamp", y="avg_risk_score",
            title="每日平均風險分數（RISK x/5）",
            labels={"timestamp": "日期", "avg_risk_score": "平均風險分數"},
            markers=True
        )
        fig_risk.add_hline(y=3.5, line_dash="dash", line_color="red", annotation_text="Risk OFF 警戒線 (3.5)")
        st.plotly_chart(fig_risk, use_container_width=True)
    with tab_dxy:
        fig_dxy = px.line(
            df_trend, x="timestamp", y="dxy",
            title="ICE DXY 美元指數趨勢",
            labels={"timestamp": "日期", "dxy": "DXY"},
            markers=True
        )
        st.plotly_chart(fig_dxy, use_container_width=True)
    with tab_etf:
        fig_etf = px.bar(
            df_trend, x="timestamp", y="etf_flow_millions",
            title="BTC ETF 資金流（億，正為流入，負為流出）",
            labels={"timestamp": "日期", "etf_flow_millions": "資金流（億）"},
            color="etf_flow_millions",
            color_continuous_scale=["#e74c3c", "#2ecc71"]
        )
        st.plotly_chart(fig_etf, use_container_width=True)

st.divider()

# ════════════════════════════════════════════════════════════════════
# 區塊 3：鏈上巨鯨資金流向
# ════════════════════════════════════════════════════════════════════
st.subheader("🐋 鏈上巨鯨資金流向 (BigQuery 實時連線)")

df_whales = load_whale_data()

if df_whales.empty:
    st.info("目前 BigQuery 資料庫中尚無巨鯨轉帳紀錄。")
else:
    fig = px.bar(
        df_whales,
        x='timestamp',
        y='amount',
        title="BTC 巨鯨大額轉帳歷史（單位：BTC）",
        labels={'timestamp': '時間', 'amount': '轉帳數量 (BTC)'},
        color='amount',
        color_continuous_scale=px.colors.sequential.Agsunset
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("查看原始數據"):
        st.dataframe(df_whales)

st.divider()

# ════════════════════════════════════════════════════════════════════
# 區塊 4：Agent 戰略觀點（預留擴充）
# ════════════════════════════════════════════════════════════════════
st.subheader("🧠 核心 Agent 戰略點評")
tab1, tab2 = st.tabs(["🛸 幣圈暗網情報 (Grok)", "🤖 AI 前沿與算力 (GPT)"])

grok_text = metrics.get("grok_summary")
gpt_text  = metrics.get("gpt_summary")

with tab1:
    if grok_text:
        st.markdown(grok_text)
    else:
        st.info("尚無幣圈情報摘要，等待第一次戰報寫入後自動顯示。")

with tab2:
    if gpt_text:
        st.markdown(gpt_text)
    else:
        st.info("尚無 AI 產業情報摘要，等待第一次戰報寫入後自動顯示。")

st.caption("Powered by CrewAI & Google Cloud BigQuery")
