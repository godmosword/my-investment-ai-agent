"""戰情室暗色主題：色盤、Plotly 佈局、自訂 CSS（由 `dashboard.py` 使用）。"""

from __future__ import annotations

import plotly.graph_objects as go

COLORS: dict[str, str] = {
    "green": "#00d2a0",
    "yellow": "#f5c542",
    "red": "#ff4b5c",
    "blue": "#3a86ff",
    "purple": "#8338ec",
    "cyan": "#22d3ee",
    "bg_card": "rgba(30, 36, 50, 0.55)",
    "bg_deep": "#0d1117",
    "border": "rgba(255,255,255,0.08)",
    "text_muted": "#8e99a4",
    "glow": "rgba(58, 134, 255, 0.35)",
}

PLOTLY_TEMPLATE = dict(
    layout=go.Layout(
        font=dict(family="DM Sans, sans-serif", color="#c9d1d9"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title_font_color="#e6edf3",
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.06)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.06)"),
        colorway=[
            COLORS["blue"],
            COLORS["green"],
            COLORS["purple"],
            COLORS["yellow"],
            COLORS["red"],
        ],
    )
)


def dashboard_inline_css(colors: dict[str, str] | None = None) -> str:
    """回傳注入 Streamlit `st.markdown(..., unsafe_allow_html=True)` 的 `<style>` 區塊。"""
    c = colors or COLORS
    return (
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
section.main > div {
  background: radial-gradient(1200px 600px at 10%% -10%%, rgba(58, 134, 255, 0.12), transparent 55%%),
              radial-gradient(900px 500px at 100%% 0%%, rgba(131, 56, 236, 0.08), transparent 50%%),
              var(--qs-bg) !important;
}
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
h1 { letter-spacing: -0.02em; }
h2, h3 {
    border-left: 4px solid %(blue)s;
    padding-left: 12px;
    margin-top: 1.25rem;
}
button[data-baseweb="tab"] {
    font-weight: 600 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    border-bottom-color: %(blue)s !important;
    color: #e6edf3 !important;
}
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
        % c
    )
