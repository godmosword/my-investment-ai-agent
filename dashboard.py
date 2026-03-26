import logging
import streamlit as st
import pandas as pd
from google.cloud import bigquery
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta, timezone
from dotenv import load_dotenv

from config import PROJECT_ID

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

load_dotenv()

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Q-Silicon 戰情室",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

_TIMEZONE_TPE = timezone(timedelta(hours=8))

# ── Auto-refresh：每 5 分鐘自動重新載入頁面 ────────────────────────────
if st_autorefresh is not None:
    st_autorefresh(interval=5 * 60 * 1000, key="auto_refresh")

# ── 統一色盤 ──────────────────────────────────────────────────────────
COLORS = {
    "green":      "#00d2a0",
    "yellow":     "#f5c542",
    "red":        "#ff4b5c",
    "blue":       "#3a86ff",
    "purple":     "#8338ec",
    "cyan":       "#22d3ee",
    "bg_card":    "rgba(30, 36, 50, 0.55)",
    "bg_deep":    "#0d1117",
    "border":     "rgba(255,255,255,0.08)",
    "text_muted": "#8e99a4",
    "glow":       "rgba(58, 134, 255, 0.35)",
}

PLOTLY_TEMPLATE = dict(
    layout=go.Layout(
        font=dict(family="DM Sans, sans-serif", color="#c9d1d9"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title_font_color="#e6edf3",
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.06)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.06)"),
        colorway=[COLORS["blue"], COLORS["green"], COLORS["purple"], COLORS["yellow"], COLORS["red"]],
    )
)

# ── 自訂 CSS ──────────────────────────────────────────────────────────
st.markdown(
    """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {
  --qs-bg: #0d1117;
  --qs-surface: rgba(22, 27, 38, 0.92);
  --qs-blue: %(blue)s;
  --qs-cyan: %(cyan)s;
}
html, body, [class*="css"]  {
  font-family: 'DM Sans', 'Noto Sans TC', system-ui, sans-serif !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  font-family: 'JetBrains Mono', ui-monospace, monospace !important;
  letter-spacing: -0.02em;
}
/* 頁面背景微漸層 */
section.main > div {
  background: radial-gradient(1200px 600px at 10%% -10%%, rgba(58, 134, 255, 0.12), transparent 55%%),
              radial-gradient(900px 500px at 100%% 0%%, rgba(131, 56, 236, 0.08), transparent 50%%),
              var(--qs-bg) !important;
}
/* KPI 卡片 */
div[data-testid="stMetric"] {
    background: linear-gradient(145deg, rgba(38, 45, 62, 0.75), rgba(22, 27, 38, 0.85)) !important;
    border: 1px solid %(border)s;
    border-radius: 14px;
    padding: 18px 20px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.25);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="stMetric"]:hover {
    border-color: rgba(58, 134, 255, 0.35);
    box-shadow: 0 0 0 1px rgba(58, 134, 255, 0.12), 0 8px 32px rgba(0,0,0,0.35);
}
div[data-testid="stMetric"] label {
    color: %(text_muted)s !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-weight: 700;
    font-size: 1.55rem !important;
}

/* 頂部 hero 條 */
.qs-hero {
    position: relative;
    padding: 1px;
    border-radius: 14px;
    margin-bottom: 0.75rem;
    background: linear-gradient(120deg, %(blue)s, %(purple)s, %(cyan)s);
    box-shadow: 0 0 40px %(glow)s;
}
.qs-hero-inner {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    padding: 12px 16px;
    border-radius: 13px;
    background: rgba(13, 17, 23, 0.92);
}
.qs-pill {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 999px;
    background: rgba(58, 134, 255, 0.2);
    color: #c9e0ff;
    border: 1px solid rgba(58, 134, 255, 0.35);
}
.qs-pill-dim {
    background: rgba(142, 153, 164, 0.12);
    color: %(text_muted)s;
    border-color: %(border)s;
}

/* Section 標題 */
h1 { letter-spacing: -0.02em; }
h2, h3 {
    border-left: 4px solid %(blue)s;
    padding-left: 12px;
    margin-top: 1.25rem;
}

/* Tab */
button[data-baseweb="tab"] {
    font-weight: 600 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom-color: %(blue)s !important;
    color: #e6edf3 !important;
}

/* Plotly 外框圓角（外層 element） */
div[data-testid="stPlotlyChart"] {
    border-radius: 12px;
    border: 1px solid %(border)s;
    overflow: hidden;
    background: rgba(0,0,0,0.15);
}

details[data-testid="stExpander"] {
    border-radius: 12px;
    border: 1px solid %(border)s;
    background: rgba(0,0,0,0.12);
}
hr {
    border-color: %(border)s !important;
    opacity: 0.45;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(20, 24, 32, 0.98), rgba(13, 17, 23, 0.98)) !important;
    border-right: 1px solid %(border)s !important;
}
section[data-testid="stSidebar"] .stCaption {
    color: %(text_muted)s;
}
/* Agent 摘要區塊 */
div.qs-agent-wrap {
    border: 1px solid %(border)s;
    border-radius: 12px;
    padding: 1rem 1.15rem;
    background: linear-gradient(180deg, rgba(32, 38, 52, 0.5), rgba(18, 22, 30, 0.65));
    margin-top: 0.5rem;
}
footer.qs-footer {
    text-align: center;
    color: %(text_muted)s;
    font-size: 0.78rem;
    margin-top: 2.5rem;
    padding: 1rem;
    border-top: 1px solid %(border)s;
    opacity: 0.85;
}
</style>
"""
    % COLORS,
    unsafe_allow_html=True,
)

st.title("🛡️ Q-Silicon 終極投資戰情室")
st.caption("自動化情報聚合 ｜ 巨鯨資金流向 ｜ AI 算力定價")
st.markdown(
    """
<div class="qs-hero"><div class="qs-hero-inner">
<span class="qs-pill">Live · BigQuery</span>
<span class="qs-pill qs-pill-dim">Plotly</span>
<span class="qs-pill qs-pill-dim">Streamlit</span>
</div></div>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def _get_bq_client() -> bigquery.Client:
    """BigQuery Client singleton：整個 Streamlit 進程只建立一次。"""
    return bigquery.Client(project=PROJECT_ID)


# ── 預先計算 Plotly 佈局 kwargs（避免每次渲染重複序列化）──────────────
_LAYOUT_KWARGS: dict = PLOTLY_TEMPLATE["layout"].to_plotly_json()


def _style_plotly(fig, *, height: int | None = None) -> None:
    """統一暗色主題、hover、圖例位置。"""
    fig.update_layout(**_LAYOUT_KWARGS)
    fig.update_layout(
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(16, 20, 28, 0.94)",
            font_size=13,
            font_family="DM Sans, sans-serif",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    if height is not None:
        fig.update_layout(height=height)

# ── Sidebar：全域篩選與設定 ──────────────────────────────────────────
with st.sidebar:
    st.header("篩選設定")
    RANGE_OPTIONS = {"7 天": 7, "14 天": 14, "30 天": 30, "90 天": 90}
    selected_range = st.radio("趨勢圖時間範圍", list(RANGE_OPTIONS.keys()), index=2, horizontal=True)
    trend_days = RANGE_OPTIONS[selected_range]
    st.divider()
    if st.button("Refresh Now", key="manual_refresh"):
        st.cache_data.clear()
        st.rerun()
    _now_tpe = datetime.now(_TIMEZONE_TPE)
    st.caption(f"Last refresh: {_now_tpe.strftime('%H:%M:%S')} TPE")
    st.caption("🛡️ Q-Silicon 戰情室 v3")


# ── 讀取每日指標（動態 KPI 來源）─────────────────────────────────────
@st.cache_data(ttl=300)
def load_daily_metrics() -> dict:
    """從 BigQuery daily_metrics 取最新兩筆紀錄，回傳 dict（含日環比 delta）。"""
    try:
        client = _get_bq_client()
        query = f"""
            SELECT timestamp, dxy, etf_flow_millions, avg_risk_score,
                   gpu_b200_price, grok_summary, gpt_summary, mvrv_z_score,
                   sentiment_score, sopr, exchange_netflow, regime_score
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
            "sentiment_score":  latest.get("sentiment_score"),
            "sopr":             latest.get("sopr"),
            "exchange_netflow": latest.get("exchange_netflow"),
            "regime_score":     latest.get("regime_score"),
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

# 根據平均風險分數判斷市場模式（與日報 neutral / risk_on / risk_off 三態對齊）
if avg_risk is not None:
    if avg_risk >= 3.5:
        regime_label = "🔴 Risk OFF"
        regime_delta = "高度警戒 · 防禦"
        regime_color = "inverse"
    elif avg_risk >= 2.5:
        regime_label = "🟡 Neutral"
        regime_delta = "結構觀望 · 控倉"
        regime_color = "off"
    else:
        regime_label = "🟢 Risk ON"
        regime_delta = "風險可控 · 找催化"
        regime_color = "normal"
else:
    regime_label = "N/A"
    regime_delta = "尚無數據"
    regime_color = "off"

mvrv_val   = metrics.get("mvrv_z_score")

dxy_display = f"{dxy_val:.2f}" if dxy_val is not None else "N/A"
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
delta_etf  = metrics.get("delta_etf")
delta_mvrv = metrics.get("delta_mvrv")

dxy_delta_str  = f"{delta_dxy:+.2f}" if delta_dxy is not None else None
etf_delta_str  = f"{delta_etf:+.1f}億" if delta_etf is not None else None
mvrv_delta_str = f"{delta_mvrv:+.2f}" if delta_mvrv is not None else None

st.subheader("財經儀表板")
st.caption("宏觀 → 幣圈 → AI")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="【宏觀】ICE DXY", value=dxy_display, delta=dxy_delta_str, delta_color="inverse")
with col2:
    st.metric(label="【幣圈】BTC ETF 資金流", value=etf_display, delta=etf_delta_str, delta_color=etf_color)
with col3:
    st.metric(label="【幣圈】MVRV Z-Score", value=mvrv_display, delta=mvrv_signal or mvrv_delta_str, delta_color="off")
with col4:
    st.metric(label="當前市場模式", value=regime_label, delta=regime_delta, delta_color=regime_color)

# 最後更新時間
if metrics.get("timestamp"):
    st.caption(f"數據更新時間：{metrics['timestamp']}")

# ════════════════════════════════════════════════════════════════════
# 鏈上情緒與衍生品（日報 / BQ 同源 + 工具層資金費率）
# ════════════════════════════════════════════════════════════════════
st.subheader("🔗 鏈上情緒與衍生品快照")
st.caption(
    "SOPR、情緒分數、交易所淨流向、regime_score 來自 **daily_metrics**（與 `bigquery_writer` 萃取一致）；"
    "BTC 資金費率為 **即時** 呼叫 `coinglass_data_tool`／Binance 備援（非 BQ 快取）。"
)

_s = metrics.get("sentiment_score")
_sopr = metrics.get("sopr")
_net = metrics.get("exchange_netflow")
_rs = metrics.get("regime_score")

def _fmt_opt(v, nd=3, suffix=""):
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.{nd}f}{suffix}"
    except (TypeError, ValueError):
        return "N/A"

oc1, oc2, oc3, oc4 = st.columns(4)
with oc1:
    st.metric(label="SOPR（鏈上）", value=_fmt_opt(_sopr, 4), help=">1 偏獲利了結；<1 偏虧損拋售")
with oc2:
    st.metric(label="情緒分數", value=_fmt_opt(_s, 3), help="約 -1～+1，來自日報管線情緒工具")
with oc3:
    st.metric(label="交易所淨流向", value=_fmt_opt(_net, 2), help="單位依管線萃取；正偏流入、負偏流出")
with oc4:
    st.metric(label="Regime score", value=_fmt_opt(_rs, 2), help="與日報 regime 評分卡相關之結構分數")

@st.cache_data(ttl=300)
def _dashboard_btc_funding_text() -> str:
    try:
        from tools import coinglass_data_tool  # noqa: PLC0415

        return str(coinglass_data_tool.run("funding_rate") or "").strip()
    except Exception as e:
        logger.warning("dashboard funding_rate tool failed: %s", e)
        return f"[DATA_MISSING:funding_rate] {e}"


with st.expander("📌 BTC 資金費率（Funding · 工具層即時）", expanded=False):
    _ft = _dashboard_btc_funding_text()
    st.code(_ft[:4000] if len(_ft) > 4000 else _ft, language="text")

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
                {"range": [0, 2.5],   "color": COLORS["green"]},
                {"range": [2.5, 3.5], "color": COLORS["yellow"]},
                {"range": [3.5, 5],   "color": COLORS["red"]},
            ],
            "threshold": {
                "line": {"color": COLORS["red"], "width": 3},
                "thickness": 0.8,
                "value": 3.5,
            },
        },
        title={"text": "平均風險分數", "font": {"size": 18, "color": "#e6edf3"}},
    ))
    _style_plotly(fig_gauge, height=260)
    fig_gauge.update_layout(margin=dict(t=60, b=20, l=30, r=30))
    st.plotly_chart(fig_gauge, use_container_width=True)

with info_col:
    st.markdown("**風險等級說明**")
    st.markdown(
        "- 🟢 **0 ~ 2.5**：Risk ON 區 — 情緒相對穩定，可積極找結構機會\n"
        "- 🟡 **2.5 ~ 3.5**：Neutral 區 — 多空拉扯，控倉與紀律優先\n"
        "- 🔴 **3.5 ~ 5.0**：Risk OFF 區 — FUD 升溫，偏防禦與現金管理"
    )
    if avg_risk is not None:
        if avg_risk >= 3.5:
            st.error(f"當前風險 {avg_risk:.1f}/5 — 建議減倉或對沖")
        elif avg_risk >= 2.5:
            st.warning(f"當前風險 {avg_risk:.1f}/5 — 中性觀望，嚴守風險預算")
        else:
            st.success(f"當前風險 {avg_risk:.1f}/5 — 市場相對友善（仍須單筆風控）")

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
            SELECT timestamp, avg_risk_score, dxy, etf_flow_millions, mvrv_z_score,
                   sentiment_score, sopr, exchange_netflow
            FROM `{PROJECT_ID}.market_data.daily_metrics`
            WHERE timestamp >= '{cutoff}'
            ORDER BY timestamp ASC
        """
        return client.query(query).to_dataframe()
    except Exception as e:
        logger.warning("load_risk_trend BigQuery failed: %s", e)
        return pd.DataFrame()

df_trend = load_risk_trend(days=trend_days)

if df_trend.empty:
    st.info("尚無歷史指標數據，等待第一次戰報寫入後自動顯示。")
else:
    tab_dxy, tab_etf, tab_mvrv, tab_risk, tab_sopr, tab_sent, tab_net = st.tabs(
        ["💵 宏觀 DXY", "💸 幣圈 ETF 資金流", "🔗 幣圈 MVRV", "⚠️ 影響指數", "⛓ SOPR", "🎭 情緒", "🏦 交易所淨流"]
    )
    with tab_dxy:
        fig_dxy = px.line(
            df_trend, x="timestamp", y="dxy",
            title="ICE DXY 美元指數趨勢",
            labels={"timestamp": "日期", "dxy": "DXY"},
            markers=True, color_discrete_sequence=[COLORS["blue"]],
        )
        fig_dxy.update_traces(
            line=dict(width=2.6, shape="spline", smoothing=0.35),
            marker=dict(size=8, line=dict(width=0)),
        )
        _style_plotly(fig_dxy, height=420)
        st.plotly_chart(fig_dxy, use_container_width=True)
    with tab_etf:
        fig_etf = px.bar(
            df_trend, x="timestamp", y="etf_flow_millions",
            title="BTC ETF 資金流（億，正為流入，負為流出）",
            labels={"timestamp": "日期", "etf_flow_millions": "資金流（億）"},
            color="etf_flow_millions",
            color_continuous_scale=[COLORS["red"], "#1a1f2e", COLORS["green"]],
        )
        fig_etf.update_traces(marker_line_width=0, opacity=0.92)
        _style_plotly(fig_etf, height=420)
        st.plotly_chart(fig_etf, use_container_width=True)
    with tab_mvrv:
        fig_mvrv = px.line(
            df_trend, x="timestamp", y="mvrv_z_score",
            title="BTC MVRV Z-Score 鏈上估值趨勢",
            labels={"timestamp": "日期", "mvrv_z_score": "MVRV Z-Score"},
            markers=True, color_discrete_sequence=[COLORS["purple"]],
        )
        fig_mvrv.update_traces(
            line=dict(width=2.6, shape="spline", smoothing=0.35),
            marker=dict(size=8, line=dict(width=0)),
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
        _style_plotly(fig_mvrv, height=440)
        st.plotly_chart(fig_mvrv, use_container_width=True)
        st.caption("MVRV Z-Score > 7：歷史頂部區域 ｜ 3~7：看漲但需留意過熱 ｜ 0~3：健康多頭 ｜ < 0：底部積累")
    with tab_risk:
        fig_risk = px.line(
            df_trend, x="timestamp", y="avg_risk_score",
            title="每日影響指數（強利空=5 … 強利多=1）",
            labels={"timestamp": "日期", "avg_risk_score": "影響指數"},
            markers=True, color_discrete_sequence=[COLORS["yellow"]],
        )
        fig_risk.update_traces(
            line=dict(width=2.6, shape="spline", smoothing=0.35),
            marker=dict(size=8, line=dict(width=0)),
        )
        fig_risk.add_hline(
            y=3.5, line_dash="dash", line_color=COLORS["red"],
            annotation_text="Risk OFF 警戒線 (3.5)",
            annotation_font_color=COLORS["red"],
        )
        fig_risk.add_hline(
            y=2.5, line_dash="dot", line_color=COLORS["blue"],
            annotation_text="Neutral 下緣 (2.5)",
            annotation_font_color=COLORS["blue"],
        )
        _style_plotly(fig_risk, height=420)
        st.plotly_chart(fig_risk, use_container_width=True)
    with tab_sopr:
        if "sopr" in df_trend.columns and df_trend["sopr"].notna().any():
            fig_so = px.line(
                df_trend.dropna(subset=["sopr"]),
                x="timestamp", y="sopr",
                title="BTC SOPR（日報萃取 · daily_metrics）",
                labels={"timestamp": "日期", "sopr": "SOPR"},
                markers=True, color_discrete_sequence=[COLORS["cyan"]],
            )
            fig_so.update_traces(line=dict(width=2.4, shape="spline", smoothing=0.3))
            _style_plotly(fig_so, height=400)
            st.plotly_chart(fig_so, use_container_width=True)
            st.caption("資料來源：戰報寫入 BQ 之鏈上摘要欄位；全 null 時代表尚未有有效萃取。")
        else:
            st.info("尚無 SOPR 歷史序列（欄位全空或尚無戰報寫入）。")
    with tab_sent:
        if "sentiment_score" in df_trend.columns and df_trend["sentiment_score"].notna().any():
            fig_se = px.line(
                df_trend.dropna(subset=["sentiment_score"]),
                x="timestamp", y="sentiment_score",
                title="情緒分數（日報管線 · daily_metrics）",
                labels={"timestamp": "日期", "sentiment_score": "情緒 (-1~+1)"},
                markers=True, color_discrete_sequence=[COLORS["purple"]],
            )
            fig_se.update_traces(line=dict(width=2.4, shape="spline", smoothing=0.3))
            _style_plotly(fig_se, height=400)
            st.plotly_chart(fig_se, use_container_width=True)
        else:
            st.info("尚無情緒分數歷史序列。")
    with tab_net:
        if "exchange_netflow" in df_trend.columns and df_trend["exchange_netflow"].notna().any():
            fig_nf = px.bar(
                df_trend.dropna(subset=["exchange_netflow"]),
                x="timestamp", y="exchange_netflow",
                title="交易所淨流向（日報萃取）",
                labels={"timestamp": "日期", "exchange_netflow": "淨流向"},
                color="exchange_netflow",
                color_continuous_scale=[COLORS["red"], "#1a1f2e", COLORS["green"]],
            )
            fig_nf.update_traces(marker_line_width=0, opacity=0.9)
            _style_plotly(fig_nf, height=400)
            st.plotly_chart(fig_nf, use_container_width=True)
        else:
            st.info("尚無交易所淨流向歷史序列。")

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
        x="timestamp",
        y="amount",
        title="BTC 巨鯨大額轉帳歷史（單位：BTC）",
        labels={"timestamp": "時間", "amount": "轉帳數量 (BTC)"},
        color="amount",
        color_continuous_scale=[COLORS["cyan"], COLORS["purple"], COLORS["red"]],
    )
    fig.update_traces(marker_line_width=0, opacity=0.9)
    _style_plotly(fig, height=400)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("查看原始數據"):
        st.dataframe(df_whales)

st.divider()

# ════════════════════════════════════════════════════════════════════
# 區塊 4：Agent 戰略觀點（預留擴充）
# ════════════════════════════════════════════════════════════════════
st.subheader("🏢 公司戰情（試點 · Multi-agent）")
try:
    from crew_company import load_company_war_room_snapshot

    _co = load_company_war_room_snapshot()
except Exception:
    _co = None
if _co:
    st.caption(f"最近更新：{_co.get('updated_at', 'N/A')} ｜ 來源：{_co.get('crew', 'N/A')}")
    st.text_area("Growth 敘事快照（唯讀）", value=str(_co.get("growth_raw", "")), height=220, disabled=True)
else:
    st.info(
        "尚無快照：於主機設定 `COMPANY_CREW_ENABLED=1` 並執行 `python main.py` 後，"
        "Growth crew 會寫入 `.qsilicon/company_run_latest.json`（勿提交 git）。"
    )
with st.expander("Arbiter／四職能 schema（設計預覽）"):
    try:
        from company_ops_schemas import ArbiterResolution, DepartmentMemo

        _demo = DepartmentMemo(
            department="growth",
            summary="（範例）本週敘事主軸：開源模型下載榜變化。",
            confidence=0.6,
            open_questions=["是否需追加產品路線對齊？"],
        )
        _res = ArbiterResolution(
            headline="（範例）優先完成日報穩定性，其次實驗 Growth A/B。",
            priorities=["日報 Gate", "PWA KPI 對齊"],
            conflicts=["Growth 想加速 vs Engineering 技術債"],
            needs_data=["上週轉換率"],
        )
        st.json({"memo_demo": _demo.model_dump(), "arbiter_demo": _res.model_dump()})
    except Exception as e:
        st.warning(f"無法載入 schema 預覽：{e}")

st.divider()

st.subheader("🧠 核心 Agent 戰略點評")
tab1, tab2 = st.tabs(["🛸 幣圈暗網情報 (Grok)", "🤖 AI 前沿與算力 (GPT)"])

grok_text = metrics.get("grok_summary")
gpt_text  = metrics.get("gpt_summary")

with tab1:
    if grok_text:
        st.markdown('<div class="qs-agent-wrap">', unsafe_allow_html=True)
        st.markdown(grok_text)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("尚無幣圈情報摘要，等待第一次戰報寫入後自動顯示。")

with tab2:
    if gpt_text:
        st.markdown('<div class="qs-agent-wrap">', unsafe_allow_html=True)
        st.markdown(gpt_text)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("尚無 AI 產業情報摘要，等待第一次戰報寫入後自動顯示。")

st.markdown(
    '<footer class="qs-footer">Q-Silicon · CrewAI pipeline · BigQuery · Plotly · Streamlit v3</footer>',
    unsafe_allow_html=True,
)
