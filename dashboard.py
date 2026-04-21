import json
import logging
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st
from google.cloud import bigquery
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta, timezone
from dotenv import load_dotenv

from config import (
    GATE_FAILURE_LOG_TABLE,
    LLM_RUN_LOG_TABLE,
    PROJECT_ID,
    RECOMMENDATIONS_TABLE,
)

from dashboard.theme import COLORS, PLOTLY_TEMPLATE, dashboard_inline_css
from dashboard.snapshot_payload import load_dashboard_symbol_snapshot_payload

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

_DASH_REFRESH_SEC = max(
    60, int((os.getenv("DASHBOARD_AUTO_REFRESH_SEC") or "300").strip())
)

# ── Auto-refresh：`DASHBOARD_AUTO_REFRESH_SEC`（預設 300）──────────────────
if st_autorefresh is not None:
    st_autorefresh(interval=_DASH_REFRESH_SEC * 1000, key="auto_refresh")

st.markdown(dashboard_inline_css(COLORS), unsafe_allow_html=True)

_LAYOUT_KWARGS: dict = PLOTLY_TEMPLATE["layout"].to_plotly_json()

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
    selected_range = st.radio(
        "趨勢圖時間範圍", list(RANGE_OPTIONS.keys()), index=2, horizontal=True
    )
    trend_days = RANGE_OPTIONS[selected_range]
    st.divider()
    if st.button("Refresh Now", key="manual_refresh"):
        st.cache_data.clear()
        st.rerun()
    _now_tpe = datetime.now(_TIMEZONE_TPE)
    st.caption(f"Last refresh: {_now_tpe.strftime('%H:%M:%S')} TPE")
    st.caption(
        f"自動刷新間隔：**{_DASH_REFRESH_SEC}s**（`DASHBOARD_AUTO_REFRESH_SEC`）"
    )
    st.caption("🛡️ Q-Silicon 戰情室 v4")


# ── 讀取每日指標（動態 KPI 來源）─────────────────────────────────────
@st.cache_data(ttl=120)
def _dashboard_symbol_snapshot_payload(
    symbol: str, days: int, recommendation_limit: int
) -> dict[str, object]:
    """Same JSON shape as ``GET /api/symbols/{symbol}/snapshot`` (BQ + yfinance).

    If ``SYMBOL_SNAPSHOT_HTTP_BASE`` is set (e.g. ``http://127.0.0.1:8000``), calls the
    FastAPI process over HTTP so Streamlit can split from the API container. Otherwise
    uses ``symbol_snapshot_service.build_symbol_snapshot`` with this process's BQ client.
    """
    from symbol_snapshot_service import build_symbol_snapshot, validate_symbol_for_snapshot  # noqa: PLC0415

    try:
        return load_dashboard_symbol_snapshot_payload(
            symbol=symbol,
            days=days,
            recommendation_limit=recommendation_limit,
            http_base=os.getenv("SYMBOL_SNAPSHOT_HTTP_BASE") or "",
            validate_symbol=validate_symbol_for_snapshot,
            build_snapshot=build_symbol_snapshot,
            client_factory=_get_bq_client,
        )
    except Exception as exc:  # pragma: no cover - network / BQ env dependent
        logger.warning("dashboard symbol snapshot (direct BQ) failed: %s", exc)
        return {"_error": str(exc)}


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
            "timestamp": latest.get("timestamp"),
            "dxy": latest.get("dxy"),
            "etf_flow": latest.get("etf_flow_millions"),
            "avg_risk_score": latest.get("avg_risk_score"),
            "gpu_b200_price": latest.get("gpu_b200_price"),
            "grok_summary": latest.get("grok_summary"),
            "gpt_summary": latest.get("gpt_summary"),
            "mvrv_z_score": latest.get("mvrv_z_score"),
            "delta_dxy": _delta("dxy"),
            "delta_etf": _delta("etf_flow_millions"),
            "delta_risk": _delta("avg_risk_score"),
            "delta_b200": _delta("gpu_b200_price"),
            "delta_mvrv": _delta("mvrv_z_score"),
            "sentiment_score": latest.get("sentiment_score"),
            "sopr": latest.get("sopr"),
            "exchange_netflow": latest.get("exchange_netflow"),
            "regime_score": latest.get("regime_score"),
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


def _dash_repo_root() -> Path:
    return Path(__file__).resolve().parent


def _dash_read_json_if_exists(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _dash_compact_yyyymmdd(report_date: str) -> str:
    return report_date.replace("-", "")


def _dash_daily_brief_explicit_paths(report_date: str) -> list[Path]:
    paths: list[Path] = []
    env_dir = (os.getenv("DAILY_BRIEF_JSON_DIR") or "").strip()
    if env_dir:
        paths.append(Path(env_dir).expanduser().resolve() / f"{report_date}.json")
    paths.append(
        _dash_repo_root() / ".qsilicon" / "daily_brief_reports" / f"{report_date}.json"
    )
    return paths


def _dash_load_daily_brief_from_logs_run(
    report_date: str,
) -> tuple[dict | None, str | None]:
    logs_dir = _dash_repo_root() / "logs"
    if not logs_dir.is_dir():
        return None, None
    compact = _dash_compact_yyyymmdd(report_date)
    for folder in sorted(logs_dir.glob("run_*"), reverse=True):
        m = re.match(r"run_(\d{8})_", folder.name)
        if not m or m.group(1) != compact:
            continue
        path = folder / "raw_data.json"
        data = _dash_read_json_if_exists(path)
        if data:
            try:
                rel = path.relative_to(_dash_repo_root())
            except ValueError:
                rel = path
            return data, str(rel).replace("\\", "/")
    return None, None


def _dash_try_load_daily_brief(report_date: str) -> tuple[dict | None, str | None]:
    root = _dash_repo_root().resolve()
    for path in _dash_daily_brief_explicit_paths(report_date):
        data = _dash_read_json_if_exists(path)
        if data:
            try:
                src = str(path.resolve().relative_to(root)).replace("\\", "/")
            except ValueError:
                src = str(path)
            return data, src
    return _dash_load_daily_brief_from_logs_run(report_date)


@st.cache_data(ttl=120)
def _bq_llm_profile_stats(days: int = 30) -> pd.DataFrame:
    try:
        client = _get_bq_client()
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("d", "INT64", int(days)),
            ]
        )
        query = f"""
            SELECT
                COALESCE(profile, 'full') AS profile,
                COUNT(*) AS run_count,
                COUNTIF(gate_passed) AS gate_ok_count,
                COUNT(DISTINCT DATE(timestamp)) AS distinct_days
            FROM `{LLM_RUN_LOG_TABLE}`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @d DAY)
            GROUP BY profile
            ORDER BY run_count DESC
        """
        return client.query(query, job_config=job_config).to_dataframe()
    except Exception as exc:
        logger.warning("dashboard llm_run_log aggregate failed: %s", exc)
        return pd.DataFrame()


@st.cache_data(ttl=120)
def _bq_gate_failures_recent(days: int = 7) -> pd.DataFrame:
    try:
        client = _get_bq_client()
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("d", "INT64", int(days)),
            ]
        )
        query = f"""
            SELECT
                timestamp,
                profile,
                attempt,
                blocking_count,
                warning_count,
                issue_count,
                issues_preview,
                fingerprint
            FROM `{GATE_FAILURE_LOG_TABLE}`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @d DAY)
            ORDER BY timestamp DESC
            LIMIT 500
        """
        return client.query(query, job_config=job_config).to_dataframe()
    except Exception as exc:
        logger.warning("dashboard gate_failure_log query failed: %s", exc)
        return pd.DataFrame()


def render_profile_tab() -> None:
    """依 profile 聚合 `llm_run_log`（近 30 日）。"""
    st.subheader("Profile / LLM 執行紀錄")
    st.caption("資料來源：`market_data.llm_run_log` · 近 **30** 日")
    df = _bq_llm_profile_stats(30)
    if df.empty:
        st.warning("無法讀取 LLM 聚合（BigQuery 未設定、憑證缺失或表為空）。")
        return
    fig = px.bar(
        df,
        x="profile",
        y="run_count",
        color="profile",
        title="各 profile LLM 執行次數",
        labels={"run_count": "執行次數", "profile": "Profile"},
    )
    _style_plotly(fig, height=360)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def render_gate_tab() -> None:
    """近 7 日 `gate_failure_log` 事件表與每日筆數。"""
    st.subheader("Gate 失敗事件")
    st.caption("資料來源：`market_data.gate_failure_log` · 近 **7** 日")
    df = _bq_gate_failures_recent(7)
    if df.empty:
        st.info("近 7 日無 Gate 失敗紀錄，或無法連線 BigQuery。")
        return
    ts = pd.to_datetime(df["timestamp"], utc=True)
    daily = ts.dt.tz_convert(_TIMEZONE_TPE).dt.date.value_counts().sort_index()
    fig = px.bar(
        x=daily.index.astype(str),
        y=daily.values,
        labels={"x": "日（TPE）", "y": "事件數"},
        title="每日 Gate 失敗事件數",
    )
    fig.update_traces(marker_color=COLORS["cyan"])
    _style_plotly(fig, height=300)
    st.plotly_chart(fig, use_container_width=True)
    show = df[
        [
            "timestamp",
            "profile",
            "blocking_count",
            "warning_count",
            "issue_count",
            "issues_preview",
        ]
    ].copy()
    st.dataframe(show, use_container_width=True, hide_index=True)


def render_roundtable_tab() -> None:
    """掃描本機／環境目錄中含 `current_affairs_roundtable` 的日報 JSON。"""
    st.subheader("時事多觀點（Roundtable）")
    st.caption(
        "掃描 `DAILY_BRIEF_JSON_DIR`、`.qsilicon/daily_brief_reports/`、"
        "`logs/run_YYYYMMDD_*/raw_data.json` · 近 **14** 日日曆日"
    )
    with st.expander("ℹ️ 數字口徑（OHLC／quote／BQ）", expanded=False):
        st.markdown(
            """
**K 線（`price_series`）**：yfinance 日線 OHLC，供 Terminal 圖表；進程快取約 **3 分鐘**。  
**Last／漲跌幅（`/api/symbols/{symbol}/quote`）**：另一條 yfinance 路徑，快取約 **45 秒** — 可能與 OHLC 尾根 **略有差**，payload 內 **`price_alignment`** 會標示是否對齊。  
**結構欄位（`latest_metrics`／`history`）**：來自 **BigQuery**，與日報指標萃取同源；**時間戳不一定等同** yfinance 最後一根 bar。  

詳見 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)「視覺化與數字段語意」與 [`visualization_plan.md`](docs/architecture/visualization_plan.md) 階段 A。
            """.strip()
        )
    _def_sym = (os.getenv("DASHBOARD_SYMBOL_FOCUS") or "BTC").strip().upper()
    _c1, _c2 = st.columns([1, 1])
    with _c1:
        _snap_sym = st.text_input("代號", value=_def_sym, key="qs_dash_snap_symbol")
    with _c2:
        _snap_days = st.number_input(
            "歷史天數",
            min_value=7,
            max_value=180,
            value=30,
            step=1,
            key="qs_dash_snap_days",
        )
    if st.button("載入快照", key="qs_dash_snap_load"):
        _pl = _dashboard_symbol_snapshot_payload(_snap_sym, int(_snap_days), 12)
        st.session_state["_qs_last_symbol_snapshot"] = _pl
    if "_qs_last_symbol_snapshot" in st.session_state:
        _pl = st.session_state["_qs_last_symbol_snapshot"]
        if isinstance(_pl, dict) and _pl.get("_error"):
            st.warning(str(_pl["_error"]))
        elif isinstance(_pl, dict):
            st.success(
                f"**{_pl.get('symbol', '?')}** · as_of `{_pl.get('as_of')}` · "
                f"recommendations **{len(_pl.get('recommendations') or [])}** · "
                f"report_links **{len(_pl.get('report_links') or [])}**"
            )
            _lm = _pl.get("latest_metrics") or {}
            _pa = (
                _pl.get("price_alignment")
                if isinstance(_pl.get("price_alignment"), dict)
                else {}
            )
            if _pa:
                _al = _pa.get("aligned")
                if _al is False:
                    st.warning(
                        "**price_alignment**：OHLC 尾端 close 與 `/quote` last 不一致（皆 yfinance，可能為快取邊界）。"
                        f" 尾端 close `{_pa.get('ohlc_last_close')}` vs quote `{_pa.get('quote_last')}`。"
                    )
                elif _al is True:
                    st.caption(
                        "price_alignment：OHLC 尾端與 quote last 一致（yfinance 交叉檢）。"
                    )
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Risk /5", f"{_lm.get('avg_risk_score', '—')}")
            with m2:
                st.metric("MVRV Z", f"{_lm.get('mvrv_z_score', '—')}")
            with m3:
                st.metric("Sentiment", f"{_lm.get('sentiment_score', '—')}")
            with m4:
                st.metric("DXY", f"{_lm.get('dxy', '—')}")
            with st.expander("完整 JSON（除錯）", expanded=False):
                st.json(_pl)

    found: list[dict[str, object]] = []
    for i in range(14):
        d = date.today() - timedelta(days=i)
        ds = d.isoformat()
        data, src = _dash_try_load_daily_brief(ds)
        if not data:
            continue
        rt = data.get("current_affairs_roundtable")
        if not rt or not isinstance(rt, dict):
            continue
        topic = str(rt.get("topic") or "").strip() or "（無 topic）"
        voices = rt.get("voices") or []
        vn = len(voices) if isinstance(voices, list) else 0
        found.append(
            {"date": ds, "topic": topic, "voices_n": vn, "source": src or "", "raw": rt}
        )

    if not found:
        st.info("近 14 日未找到含 `current_affairs_roundtable` 的日報 JSON。")
        return

    for item in found:
        rt = item["raw"]
        topic = str(rt.get("topic") or "").strip() or "（無 topic）"
        exp_title = f"{item['date']} · {topic[:52]}"
        with st.expander(exp_title, expanded=False):
            st.caption(f"來源：`{item['source']}` · voices：**{item['voices_n']}**")
            consensus = rt.get("consensus")
            if consensus:
                st.markdown("##### 共識")
                st.markdown(str(consensus))
            unresolved = rt.get("unresolved") or []
            if isinstance(unresolved, list) and unresolved:
                st.markdown("##### 待解議題")
                for line in unresolved[:16]:
                    st.markdown(f"- {line}")
            voices = rt.get("voices") or []
            if isinstance(voices, list) and voices:
                st.markdown("##### 多觀點")
                for voice in voices[:12]:
                    if not isinstance(voice, dict):
                        st.markdown(f"- {voice}")
                        continue
                    role = voice.get("role") or "—"
                    vp = voice.get("viewpoint") or ""
                    diss = voice.get("disagreement")
                    st.markdown(f"**{role}** · {vp}")
                    if diss:
                        st.caption(f"分歧：{diss}")


def render_overview() -> None:
    """Overview：既有戰情室主流程（KPI、趨勢、巨鯨、公司戰情、Grok/GPT）。"""
    # ════════════════════════════════════════════════════════════════════
    # 區塊 1：核心市場模式 KPI（動態讀取）
    # ════════════════════════════════════════════════════════════════════
    metrics = load_daily_metrics()

    avg_risk = metrics.get("avg_risk_score")
    dxy_val = metrics.get("dxy")
    etf_val = metrics.get("etf_flow")

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

    mvrv_val = metrics.get("mvrv_z_score")

    dxy_display = f"{dxy_val:.2f}" if dxy_val is not None else "N/A"
    etf_display = (
        f"-${abs(etf_val):.0f}億"
        if etf_val is not None and etf_val < 0
        else f"+${etf_val:.0f}億"
        if etf_val is not None
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
        mvrv_signal = None

    delta_dxy = metrics.get("delta_dxy")
    delta_etf = metrics.get("delta_etf")
    delta_mvrv = metrics.get("delta_mvrv")

    dxy_delta_str = f"{delta_dxy:+.2f}" if delta_dxy is not None else None
    etf_delta_str = f"{delta_etf:+.1f}億" if delta_etf is not None else None
    mvrv_delta_str = f"{delta_mvrv:+.2f}" if delta_mvrv is not None else None

    st.subheader("財經儀表板")
    st.caption("宏觀 → 幣圈 → AI")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="【宏觀】ICE DXY",
            value=dxy_display,
            delta=dxy_delta_str,
            delta_color="inverse",
        )
    with col2:
        st.metric(
            label="【幣圈】BTC ETF 資金流",
            value=etf_display,
            delta=etf_delta_str,
            delta_color=etf_color,
        )
    with col3:
        st.metric(
            label="【幣圈】MVRV Z-Score",
            value=mvrv_display,
            delta=mvrv_signal or mvrv_delta_str,
            delta_color="off",
        )
    with col4:
        st.metric(
            label="當前市場模式",
            value=regime_label,
            delta=regime_delta,
            delta_color=regime_color,
        )

    # 最後更新時間
    if metrics.get("timestamp"):
        st.caption(f"數據更新時間：{metrics['timestamp']}")

    # ════════════════════════════════════════════════════════════════════
    # Symbol 快照（與 PWA /terminal + FastAPI 契約對齊）
    # ════════════════════════════════════════════════════════════════════
    with st.expander("📊 Symbol 快照（Terminal API 對齊 · 唯讀）", expanded=False):
        st.caption(
            "與 FastAPI ``GET /api/symbols/{symbol}/snapshot``（`api.py` + `symbol_snapshot_service.py`）同一 JSON 形狀。"
            "預設走 **本程序 BigQuery**；若設 **`SYMBOL_SNAPSHOT_HTTP_BASE`** 則改打已啟動的 API 服務。"
        )
        _def_sym = (os.getenv("DASHBOARD_SYMBOL_FOCUS") or "BTC").strip().upper()
        _c1, _c2 = st.columns([1, 1])
        with _c1:
            _snap_sym = st.text_input("代號", value=_def_sym, key="qs_dash_snap_symbol")
        with _c2:
            _snap_days = st.number_input(
                "歷史天數",
                min_value=7,
                max_value=180,
                value=30,
                step=1,
                key="qs_dash_snap_days",
            )
        if st.button("載入快照", key="qs_dash_snap_load"):
            _pl = _dashboard_symbol_snapshot_payload(_snap_sym, int(_snap_days), 12)
            st.session_state["_qs_last_symbol_snapshot"] = _pl
        if "_qs_last_symbol_snapshot" in st.session_state:
            _pl = st.session_state["_qs_last_symbol_snapshot"]
            if isinstance(_pl, dict) and _pl.get("_error"):
                st.warning(str(_pl["_error"]))
            elif isinstance(_pl, dict):
                st.success(
                    f"**{_pl.get('symbol', '?')}** · as_of `{_pl.get('as_of')}` · "
                    f"recommendations **{len(_pl.get('recommendations') or [])}** · "
                    f"report_links **{len(_pl.get('report_links') or [])}**"
                )
                _lm = _pl.get("latest_metrics") or {}
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("Risk /5", f"{_lm.get('avg_risk_score', '—')}")
                with m2:
                    st.metric("MVRV Z", f"{_lm.get('mvrv_z_score', '—')}")
                with m3:
                    st.metric("Sentiment", f"{_lm.get('sentiment_score', '—')}")
                with m4:
                    st.metric("DXY", f"{_lm.get('dxy', '—')}")
                with st.expander("完整 JSON（除錯）", expanded=False):
                    st.json(_pl)

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
        st.metric(
            label="SOPR（鏈上）",
            value=_fmt_opt(_sopr, 4),
            help=">1 偏獲利了結；<1 偏虧損拋售",
        )
    with oc2:
        st.metric(
            label="情緒分數",
            value=_fmt_opt(_s, 3),
            help="約 -1～+1，來自日報管線情緒工具",
        )
    with oc3:
        st.metric(
            label="交易所淨流向",
            value=_fmt_opt(_net, 2),
            help="單位依管線萃取；正偏流入、負偏流出",
        )
    with oc4:
        st.metric(
            label="Regime score",
            value=_fmt_opt(_rs, 2),
            help="與日報 regime 評分卡相關之結構分數",
        )

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
        fig_gauge = go.Figure(
            go.Indicator(
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
                    "axis": {
                        "range": [0, 5],
                        "tickwidth": 2,
                        "dtick": 1,
                        "tickcolor": "#8e99a4",
                    },
                    "bar": {"color": COLORS["blue"]},
                    "bgcolor": "rgba(0,0,0,0)",
                    "steps": [
                        {"range": [0, 2.5], "color": COLORS["green"]},
                        {"range": [2.5, 3.5], "color": COLORS["yellow"]},
                        {"range": [3.5, 5], "color": COLORS["red"]},
                    ],
                    "threshold": {
                        "line": {"color": COLORS["red"], "width": 3},
                        "thickness": 0.8,
                        "value": 3.5,
                    },
                },
                title={
                    "text": "平均風險分數",
                    "font": {"size": 18, "color": "#e6edf3"},
                },
            )
        )
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

    @st.cache_data(ttl=600)
    def load_qsrec_asset_frequency(days: int = 7) -> pd.DataFrame:
        """近 N 日 QSREC 建議資產出現次數（輪動可視化）。"""
        try:
            client = _get_bq_client()
            q = f"""
                SELECT asset, COUNT(*) AS pick_count
                FROM `{RECOMMENDATIONS_TABLE}`
                WHERE report_date >= DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL {int(days)} DAY)
                GROUP BY asset
                ORDER BY pick_count DESC
                LIMIT 40
            """
            return client.query(q).to_dataframe()
        except Exception as e:
            logger.warning("load_qsrec_asset_frequency failed: %s", e)
            return pd.DataFrame()

    df_trend = load_risk_trend(days=trend_days)

    if df_trend.empty:
        st.info("尚無歷史指標數據，等待第一次戰報寫入後自動顯示。")
    else:
        tab_dxy, tab_etf, tab_mvrv, tab_risk, tab_sopr, tab_sent, tab_net, tab_qsrec = (
            st.tabs(
                [
                    "💵 宏觀 DXY",
                    "💸 幣圈 ETF 資金流",
                    "🔗 幣圈 MVRV",
                    "⚠️ 影響指數",
                    "⛓ SOPR",
                    "🎭 情緒",
                    "🏦 交易所淨流",
                    "📌 QSREC 頻率",
                ]
            )
        )
        with tab_dxy:
            fig_dxy = px.line(
                df_trend,
                x="timestamp",
                y="dxy",
                title="ICE DXY 美元指數趨勢",
                labels={"timestamp": "日期", "dxy": "DXY"},
                markers=True,
                color_discrete_sequence=[COLORS["blue"]],
            )
            fig_dxy.update_traces(
                line=dict(width=2.6, shape="spline", smoothing=0.35),
                marker=dict(size=8, line=dict(width=0)),
            )
            _style_plotly(fig_dxy, height=420)
            st.plotly_chart(fig_dxy, use_container_width=True)
        with tab_etf:
            fig_etf = px.bar(
                df_trend,
                x="timestamp",
                y="etf_flow_millions",
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
                df_trend,
                x="timestamp",
                y="mvrv_z_score",
                title="BTC MVRV Z-Score 鏈上估值趨勢",
                labels={"timestamp": "日期", "mvrv_z_score": "MVRV Z-Score"},
                markers=True,
                color_discrete_sequence=[COLORS["purple"]],
            )
            fig_mvrv.update_traces(
                line=dict(width=2.6, shape="spline", smoothing=0.35),
                marker=dict(size=8, line=dict(width=0)),
            )
            fig_mvrv.add_hline(
                y=7,
                line_dash="dash",
                line_color=COLORS["red"],
                annotation_text="嚴重高估（7）",
                annotation_font_color=COLORS["red"],
            )
            fig_mvrv.add_hline(
                y=0,
                line_dash="dot",
                line_color=COLORS["blue"],
                annotation_text="低估積累區（0）",
                annotation_font_color=COLORS["blue"],
            )
            fig_mvrv.add_hrect(
                y0=0,
                y1=3,
                fillcolor=COLORS["green"],
                opacity=0.05,
                line_width=0,
            )
            _style_plotly(fig_mvrv, height=440)
            st.plotly_chart(fig_mvrv, use_container_width=True)
            st.caption(
                "MVRV Z-Score > 7：歷史頂部區域 ｜ 3~7：看漲但需留意過熱 ｜ 0~3：健康多頭 ｜ < 0：底部積累"
            )
        with tab_risk:
            fig_risk = px.line(
                df_trend,
                x="timestamp",
                y="avg_risk_score",
                title="每日影響指數（強利空=5 … 強利多=1）",
                labels={"timestamp": "日期", "avg_risk_score": "影響指數"},
                markers=True,
                color_discrete_sequence=[COLORS["yellow"]],
            )
            fig_risk.update_traces(
                line=dict(width=2.6, shape="spline", smoothing=0.35),
                marker=dict(size=8, line=dict(width=0)),
            )
            fig_risk.add_hline(
                y=3.5,
                line_dash="dash",
                line_color=COLORS["red"],
                annotation_text="Risk OFF 警戒線 (3.5)",
                annotation_font_color=COLORS["red"],
            )
            fig_risk.add_hline(
                y=2.5,
                line_dash="dot",
                line_color=COLORS["blue"],
                annotation_text="Neutral 下緣 (2.5)",
                annotation_font_color=COLORS["blue"],
            )
            _style_plotly(fig_risk, height=420)
            st.plotly_chart(fig_risk, use_container_width=True)
        with tab_sopr:
            if "sopr" in df_trend.columns and df_trend["sopr"].notna().any():
                fig_so = px.line(
                    df_trend.dropna(subset=["sopr"]),
                    x="timestamp",
                    y="sopr",
                    title="BTC SOPR（日報萃取 · daily_metrics）",
                    labels={"timestamp": "日期", "sopr": "SOPR"},
                    markers=True,
                    color_discrete_sequence=[COLORS["cyan"]],
                )
                fig_so.update_traces(
                    line=dict(width=2.4, shape="spline", smoothing=0.3)
                )
                _style_plotly(fig_so, height=400)
                st.plotly_chart(fig_so, use_container_width=True)
                st.caption(
                    "資料來源：戰報寫入 BQ 之鏈上摘要欄位；全 null 時代表尚未有有效萃取。"
                )
            else:
                st.info("尚無 SOPR 歷史序列（欄位全空或尚無戰報寫入）。")
        with tab_sent:
            if (
                "sentiment_score" in df_trend.columns
                and df_trend["sentiment_score"].notna().any()
            ):
                fig_se = px.line(
                    df_trend.dropna(subset=["sentiment_score"]),
                    x="timestamp",
                    y="sentiment_score",
                    title="情緒分數（日報管線 · daily_metrics）",
                    labels={"timestamp": "日期", "sentiment_score": "情緒 (-1~+1)"},
                    markers=True,
                    color_discrete_sequence=[COLORS["purple"]],
                )
                fig_se.update_traces(
                    line=dict(width=2.4, shape="spline", smoothing=0.3)
                )
                _style_plotly(fig_se, height=400)
                st.plotly_chart(fig_se, use_container_width=True)
            else:
                st.info("尚無情緒分數歷史序列。")
        with tab_net:
            if (
                "exchange_netflow" in df_trend.columns
                and df_trend["exchange_netflow"].notna().any()
            ):
                fig_nf = px.bar(
                    df_trend.dropna(subset=["exchange_netflow"]),
                    x="timestamp",
                    y="exchange_netflow",
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
        with tab_qsrec:
            st.caption(
                "近 7 日 trade_recommendations 資產出現次數（輪動可視化；契約見 docs/DASHBOARD_CONTRACT.md）"
            )
            df_q = load_qsrec_asset_frequency(days=7)
            if df_q.empty:
                st.info("尚無 QSREC 歷史或 BigQuery 無法連線（本機可略過）。")
            else:
                fig_q = px.bar(
                    df_q.head(20),
                    x="asset",
                    y="pick_count",
                    title="近 7 日 QSREC 資產出現次數（Top 20）",
                    labels={"asset": "資產", "pick_count": "次數"},
                    color="pick_count",
                    color_continuous_scale=[
                        COLORS["blue"],
                        COLORS["purple"],
                        COLORS["yellow"],
                    ],
                )
                fig_q.update_traces(marker_line_width=0, opacity=0.92)
                _style_plotly(fig_q, height=400)
                st.plotly_chart(fig_q, use_container_width=True)
                with st.expander("完整列表（最多 40 列）"):
                    st.dataframe(df_q, use_container_width=True)

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
        st.caption(
            f"最近更新：{_co.get('updated_at', 'N/A')} ｜ 來源：{_co.get('crew', 'N/A')}"
        )
        st.text_area(
            "Growth 敘事快照（唯讀）",
            value=str(_co.get("growth_raw", "")),
            height=220,
            disabled=True,
        )
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
            st.json(
                {"memo_demo": _demo.model_dump(), "arbiter_demo": _res.model_dump()}
            )
        except Exception as e:
            st.warning(f"無法載入 schema 預覽：{e}")

    st.divider()

    st.subheader("🧠 核心 Agent 戰略點評")
    tab1, tab2 = st.tabs(["🛸 幣圈暗網情報 (Grok)", "🤖 AI 前沿與算力 (GPT)"])

    grok_text = metrics.get("grok_summary")
    gpt_text = metrics.get("gpt_summary")

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


tab_overview, tab_profile, tab_gate, tab_roundtable = st.tabs(
    ["📊 Overview", "📎 Profile / LLM", "🚧 Gate（7 日）", "🎙️ Roundtable"]
)

with tab_overview:
    render_overview()

with tab_profile:
    render_profile_tab()

with tab_gate:
    render_gate_tab()

with tab_roundtable:
    render_roundtable_tab()

st.markdown(
    '<footer class="qs-footer">Q-Silicon · CrewAI pipeline · BigQuery · Plotly · Streamlit v4</footer>',
    unsafe_allow_html=True,
)
