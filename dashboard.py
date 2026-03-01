import streamlit as st
import pandas as pd
from google.cloud import bigquery
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from dotenv import load_dotenv

from config import PROJECT_ID

load_dotenv()

st.set_page_config(page_title="Q-Silicon 戰情室", page_icon="🛡️", layout="wide")

# ── 統一色盤 ──────────────────────────────────────────────────────────
COLORS = {
    "green":      "#00d2a0",
    "yellow":     "#f5c542",
    "red":        "#ff4b5c",
    "blue":       "#3a86ff",
    "purple":     "#8338ec",
    "bg_card":    "rgba(30, 36, 50, 0.55)",
    "border":     "rgba(255,255,255,0.08)",
    "text_muted": "#8e99a4",
}

PLOTLY_TEMPLATE = dict(
    layout=go.Layout(
        font=dict(family="Inter, sans-serif", color="#c9d1d9"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title_font_color="#e6edf3",
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.06)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.06)"),
        colorway=[COLORS["blue"], COLORS["green"], COLORS["purple"], COLORS["yellow"], COLORS["red"]],
    )
)

# ── 自訂 CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
/* KPI 卡片背景 */
div[data-testid="stMetric"] {
    background: %(bg_card)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
    padding: 16px 20px;
}
div[data-testid="stMetric"] label {
    color: %(text_muted)s !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.03em;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-weight: 700;
}

/* Section 標題左側色條 */
h2, h3 {
    border-left: 4px solid %(blue)s;
    padding-left: 12px;
}

/* Tab 底線色 */
button[data-baseweb="tab"] {
    font-weight: 600 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom-color: %(blue)s !important;
}

/* Expander 圓角 */
details[data-testid="stExpander"] {
    border-radius: 10px;
    border: 1px solid %(border)s;
}

/* Divider 淡化 */
hr {
    border-color: %(border)s !important;
    opacity: 0.5;
}

/* Sidebar 底部 caption */
section[data-testid="stSidebar"] .stCaption {
    color: %(text_muted)s;
}
</style>
""" % COLORS, unsafe_allow_html=True)

st.title("🛡️ Q-Silicon 終極投資戰情室")
st.caption("自動化情報聚合 ｜ 巨鯨資金流向 ｜ AI 算力定價")


@st.cache_resource
def _get_bq_client() -> bigquery.Client:
    """BigQuery Client singleton：整個 Streamlit 進程只建立一次。"""
    return bigquery.Client(project=PROJECT_ID)


# ── 預先計算 Plotly 佈局 kwargs（避免每次渲染重複序列化）──────────────
_LAYOUT_KWARGS: dict = PLOTLY_TEMPLATE["layout"].to_plotly_json()

# ── Sidebar：全域篩選與設定 ──────────────────────────────────────────
with st.sidebar:
    st.header("篩選設定")
    RANGE_OPTIONS = {"7 天": 7, "14 天": 14, "30 天": 30, "90 天": 90}
    selected_range = st.radio("趨勢圖時間範圍", list(RANGE_OPTIONS.keys()), index=2, horizontal=True)
    trend_days = RANGE_OPTIONS[selected_range]
    st.divider()
    st.caption("🛡️ Q-Silicon 戰情室 v2")


# ── 讀取每日指標（動態 KPI 來源）─────────────────────────────────────
@st.cache_data(ttl=300)
def load_daily_metrics() -> dict:
    """從 BigQuery daily_metrics 取最新兩筆紀錄，回傳 dict（含日環比 delta）。"""
    try:
        client = _get_bq_client()
        query = f"""
            SELECT timestamp, dxy, etf_flow_millions, avg_risk_score,
                   gpu_b200_price, grok_summary, gpt_summary, mvrv_z_score
            FROM `{PROJECT_ID}.market_data.daily_metrics`
            ORDER BY timestamp DESC
            LIMIT 2
        """
        df = client.query(query).to_dataframe()
        if df.empty:
            return {}
        latest = df.iloc[0]
        prev = df.iloc[1] if len(df) > 1 else None

        def _delta(col: str):
            if prev is None:
                return None
            cur, old = latest.get(col), prev.get(col)
            if pd.notna(cur) and pd.notna(old):
                return round(cur - old, 4)
            return None

        return {
            "timestamp":        latest.get("timestamp"),
            "dxy":              latest.get("dxy"),
            "etf_flow":         latest.get("etf_flow_millions"),
            "avg_risk_score":   latest.get("avg_risk_score"),
            "gpu_b200_price":   latest.get("gpu_b200_price"),
            "grok_summary":     latest.get("grok_summary"),
            "gpt_summary":      latest.get("gpt_summary"),
            "mvrv_z_score":     latest.get("mvrv_z_score"),
            "delta_dxy":        _delta("dxy"),
            "delta_etf":        _delta("etf_flow_millions"),
            "delta_risk":       _delta("avg_risk_score"),
            "delta_b200":       _delta("gpu_b200_price"),
            "delta_mvrv":       _delta("mvrv_z_score"),
        }
    except Exception as e:
        st.warning(f"⚠️ 無法讀取 daily_metrics：{e}")
        return {}


# ── 讀取巨鯨數據 ──────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_whale_data() -> pd.DataFrame:
    try:
        client = _get_bq_client()
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
mvrv_val   = metrics.get("mvrv_z_score")

dxy_display = f"{dxy_val:.2f}" if dxy_val is not None else "N/A"
b200_display = f"${b200_val:.2f} / hr" if b200_val is not None else "N/A"
etf_display = (
    f"-${abs(etf_val):.0f}億" if etf_val is not None and etf_val < 0
    else f"+${etf_val:.0f}億" if etf_val is not None
    else "N/A"
)
etf_color = "inverse" if (etf_val is not None and etf_val < 0) else "normal"

if mvrv_val is not None:
    mvrv_display = f"{mvrv_val:.2f}"
    if mvrv_val > 7:
        mvrv_signal = "🔴 嚴重高估"
    elif mvrv_val > 3:
        mvrv_signal = "🟡 看漲過熱"
    elif mvrv_val >= 0:
        mvrv_signal = "🟢 健康多頭"
    else:
        mvrv_signal = "🔵 底部積累"
else:
    mvrv_display = "N/A"
    mvrv_signal  = None

delta_dxy  = metrics.get("delta_dxy")
delta_b200 = metrics.get("delta_b200")
delta_etf  = metrics.get("delta_etf")
delta_mvrv = metrics.get("delta_mvrv")

dxy_delta_str  = f"{delta_dxy:+.2f}" if delta_dxy is not None else None
b200_delta_str = f"{delta_b200:+.2f}" if delta_b200 is not None else None
etf_delta_str  = f"{delta_etf:+.1f}億" if delta_etf is not None else None
mvrv_delta_str = f"{delta_mvrv:+.2f}" if delta_mvrv is not None else None

st.subheader("市場模式總覽")
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric(label="當前市場模式", value=regime_label, delta=regime_delta, delta_color=regime_color)
with col2:
    st.metric(label="ICE DXY（美元指數）", value=dxy_display, delta=dxy_delta_str, delta_color="inverse")
with col3:
    st.metric(label="NVIDIA B200 租賃價", value=b200_display, delta=b200_delta_str, delta_color="inverse")
with col4:
    st.metric(label="BTC ETF 資金流", value=etf_display, delta=etf_delta_str, delta_color=etf_color)
with col5:
    st.metric(label="MVRV Z-Score", value=mvrv_display, delta=mvrv_signal or mvrv_delta_str, delta_color="off")

# 最後更新時間
if metrics.get("timestamp"):
    st.caption(f"數據更新時間：{metrics['timestamp']}")

# ════════════════════════════════════════════════════════════════════
# 風險儀表盤（Gauge）
# ════════════════════════════════════════════════════════════════════
st.divider()
gauge_col, info_col = st.columns([1, 2])

with gauge_col:
    risk_value = avg_risk if avg_risk is not None else 0
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=risk_value,
        number={"suffix": " / 5", "font": {"size": 36, "color": "#e6edf3"}},
        delta={
            "reference": risk_value - (metrics.get("delta_risk") or 0),
            "relative": False,
            "increasing": {"color": COLORS["red"]},
            "decreasing": {"color": COLORS["green"]},
        },
        gauge={
            "axis": {"range": [0, 5], "tickwidth": 2, "dtick": 1, "tickcolor": "#8e99a4"},
            "bar": {"color": COLORS["blue"]},
            "bgcolor": "rgba(0,0,0,0)",
            "steps": [
                {"range": [0, 2],   "color": COLORS["green"]},
                {"range": [2, 3.5], "color": COLORS["yellow"]},
                {"range": [3.5, 5], "color": COLORS["red"]},
            ],
            "threshold": {
                "line": {"color": COLORS["red"], "width": 3},
                "thickness": 0.8,
                "value": 3.5,
            },
        },
        title={"text": "平均風險分數", "font": {"size": 18, "color": "#e6edf3"}},
    ))
    fig_gauge.update_layout(
        height=260,
        margin={"t": 60, "b": 20, "l": 30, "r": 30},
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#c9d1d9",
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

with info_col:
    st.markdown("**風險等級說明**")
    st.markdown(
        "- 🟢 **0 ~ 2.0**：低風險，市場情緒穩定，可積極尋找機會\n"
        "- 🟡 **2.0 ~ 3.5**：中等風險，保持警覺，控制倉位\n"
        "- 🔴 **3.5 ~ 5.0**：高風險，市場 FUD 升溫，建議防禦策略"
    )
    if avg_risk is not None:
        if avg_risk >= 3.5:
            st.error(f"當前風險 {avg_risk:.1f}/5 — 建議減倉或對沖")
        elif avg_risk >= 2.0:
            st.warning(f"當前風險 {avg_risk:.1f}/5 — 謹慎操作")
        else:
            st.success(f"當前風險 {avg_risk:.1f}/5 — 市場相對安全")

st.divider()

# ════════════════════════════════════════════════════════════════════
# 區塊 2：每日指標趨勢
# ════════════════════════════════════════════════════════════════════
st.subheader("📈 每日指標趨勢")

@st.cache_data(ttl=600)
def load_risk_trend(days: int = 30) -> pd.DataFrame:
    try:
        client = _get_bq_client()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        query = f"""
            SELECT timestamp, avg_risk_score, dxy, etf_flow_millions, mvrv_z_score
            FROM `{PROJECT_ID}.market_data.daily_metrics`
            WHERE timestamp >= '{cutoff}'
            ORDER BY timestamp ASC
        """
        return client.query(query).to_dataframe()
    except Exception:
        return pd.DataFrame()

df_trend = load_risk_trend(days=trend_days)

if df_trend.empty:
    st.info("尚無歷史指標數據，等待第一次戰報寫入後自動顯示。")
else:
    tab_risk, tab_dxy, tab_etf, tab_mvrv = st.tabs(["⚠️ 平均風險分數", "💵 ICE DXY", "💸 ETF 資金流", "🔗 MVRV Z-Score"])
    with tab_risk:
        fig_risk = px.line(
            df_trend, x="timestamp", y="avg_risk_score",
            title="每日平均風險分數（RISK x/5）",
            labels={"timestamp": "日期", "avg_risk_score": "平均風險分數"},
            markers=True, color_discrete_sequence=[COLORS["yellow"]],
        )
        fig_risk.add_hline(
            y=3.5, line_dash="dash", line_color=COLORS["red"],
            annotation_text="Risk OFF 警戒線 (3.5)",
            annotation_font_color=COLORS["red"],
        )
        fig_risk.update_layout(**_LAYOUT_KWARGS)
        st.plotly_chart(fig_risk, use_container_width=True)
    with tab_dxy:
        fig_dxy = px.line(
            df_trend, x="timestamp", y="dxy",
            title="ICE DXY 美元指數趨勢",
            labels={"timestamp": "日期", "dxy": "DXY"},
            markers=True, color_discrete_sequence=[COLORS["blue"]],
        )
        fig_dxy.update_layout(**_LAYOUT_KWARGS)
        st.plotly_chart(fig_dxy, use_container_width=True)
    with tab_etf:
        fig_etf = px.bar(
            df_trend, x="timestamp", y="etf_flow_millions",
            title="BTC ETF 資金流（億，正為流入，負為流出）",
            labels={"timestamp": "日期", "etf_flow_millions": "資金流（億）"},
            color="etf_flow_millions",
            color_continuous_scale=[COLORS["red"], COLORS["green"]],
        )
        fig_etf.update_layout(**_LAYOUT_KWARGS)
        st.plotly_chart(fig_etf, use_container_width=True)
    with tab_mvrv:
        fig_mvrv = px.line(
            df_trend, x="timestamp", y="mvrv_z_score",
            title="BTC MVRV Z-Score 鏈上估值趨勢",
            labels={"timestamp": "日期", "mvrv_z_score": "MVRV Z-Score"},
            markers=True, color_discrete_sequence=[COLORS["purple"]],
        )
        fig_mvrv.add_hline(
            y=7, line_dash="dash", line_color=COLORS["red"],
            annotation_text="嚴重高估（7）",
            annotation_font_color=COLORS["red"],
        )
        fig_mvrv.add_hline(
            y=0, line_dash="dot", line_color=COLORS["blue"],
            annotation_text="低估積累區（0）",
            annotation_font_color=COLORS["blue"],
        )
        fig_mvrv.add_hrect(
            y0=0, y1=3, fillcolor=COLORS["green"], opacity=0.05, line_width=0,
        )
        fig_mvrv.update_layout(**_LAYOUT_KWARGS)
        st.plotly_chart(fig_mvrv, use_container_width=True)
        st.caption("MVRV Z-Score > 7：歷史頂部區域 ｜ 3~7：看漲但需留意過熱 ｜ 0~3：健康多頭 ｜ < 0：底部積累")

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
        color_continuous_scale=[COLORS["blue"], COLORS["purple"], COLORS["red"]],
    )
    fig.update_layout(**_LAYOUT_KWARGS)
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
