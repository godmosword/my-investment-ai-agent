"""圖表生成模組：3 Panel BTC 量化儀表板，供戰報 Telegram 發送使用。"""
import inspect
import logging
import warnings
from datetime import datetime

import requests
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
logger = logging.getLogger(__name__)

_C = {
    "btc":  "#00FF88",
    "ma":   "#FFD700",
    "vix":  "#FF4444",
    "blue": "#00BFFF",
    "red":  "#FF6666",
    "cyan": "#22d3ee",  # 與 dashboard COLORS 一致；Panel 4 資金費率軸用
}


def _remove_spines(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _ensure_showwarning_compat() -> None:
    """
    修復第三方覆寫 warnings.showwarning 的簽名不相容問題。
    Python 新版可能傳入 skip_file_prefixes；舊簽名會噴 unexpected keyword。
    """
    show = warnings.showwarning
    if getattr(show, "__qs_wrapped__", False):
        return
    try:
        sig = inspect.signature(show)
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    except Exception:
        has_kwargs = True

    if has_kwargs:
        return

    def _wrapped(message, category, filename, lineno, file=None, line=None, **kwargs):
        return show(message, category, filename, lineno, file=file, line=line)

    _wrapped.__qs_wrapped__ = True  # type: ignore[attr-defined]
    warnings.showwarning = _wrapped


def _ensure_warn_compat() -> None:
    """
    修復第三方覆寫 warnings.warn 的簽名不相容問題（缺 skip_file_prefixes）。
    """
    warn_fn = warnings.warn
    if getattr(warn_fn, "__qs_wrapped__", False):
        return
    try:
        sig = inspect.signature(warn_fn)
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    except Exception:
        has_kwargs = True

    if has_kwargs:
        return

    def _warn_wrapped(message, category=None, stacklevel=1, source=None, **kwargs):
        return warn_fn(message, category=category, stacklevel=stacklevel, source=source)

    _warn_wrapped.__qs_wrapped__ = True  # type: ignore[attr-defined]
    warnings.warn = _warn_wrapped


def _fetch_btc_funding_pct_series(limit: int = 120) -> tuple[list, list] | None:
    """Binance USDT-M 永續 BTC 資金費率（8h），回傳 (datetimes_utc, funding_pct)；失敗則 None。"""
    try:
        resp = requests.get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            params={"symbol": "BTCUSDT", "limit": min(max(limit, 10), 1000)},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list) or not data:
            return None
        from datetime import datetime, timezone

        xs: list = []
        ys: list = []
        for row in data:
            t_ms = row.get("fundingTime")
            if t_ms is None:
                continue
            xs.append(datetime.fromtimestamp(int(t_ms) / 1000.0, tz=timezone.utc))
            ys.append(float(row.get("fundingRate", 0) or 0) * 100.0)
        if not xs:
            return None
        return xs, ys
    except Exception as e:
        logger.warning("visualizer: Binance funding series failed: %s", e)
        return None


def generate_quant_chart(filename: str = "daily_chart.png") -> None:
    """
    4 Panel 量化圖表：
    Panel 1: BTC-USD 收盤價 + 20日均線
    Panel 2: VIX 恐慌指數（帶危險區上色）
    Panel 3: SPY 成交額 vs 5日均值比率（ETF 資金流代理）
    Panel 4: BTC 永續資金費率（Binance 公開 API，非 LLM）
    """
    try:
        _ensure_warn_compat()
        _ensure_showwarning_compat()
        warnings.filterwarnings("ignore", message=r"Glyph .* missing from font\(s\) DejaVu Sans\.")
        btc = yf.download("BTC-USD", period="60d", interval="1d", progress=False, auto_adjust=True)
        vix = yf.download("^VIX",    period="60d", interval="1d", progress=False, auto_adjust=True)
        spy = yf.download("SPY",     period="65d", interval="1d", progress=False, auto_adjust=True)

        if btc.empty or vix.empty or spy.empty:
            logger.warning("visualizer: 資料不足，跳過圖表生成。")
            _fallback_chart(btc, vix, filename)
            return

        btc_close = btc["Close"].squeeze()
        vix_close = vix["Close"].squeeze()

        spy_close  = spy["Close"].squeeze()
        spy_vol    = spy["Volume"].squeeze()
        spy_dollar = (spy_close * spy_vol).dropna()
        spy_avg5   = spy_dollar.rolling(5).mean()
        spy_ratio  = (spy_dollar / spy_avg5).dropna()

        common = btc_close.index.intersection(vix_close.index).sort_values()
        if len(common) < 10:
            logger.warning("visualizer: 共同日期不足，退回雙軸圖。")
            _fallback_chart(btc, vix, filename)
            return

        btc_aligned = btc_close.reindex(common).ffill().bfill()
        vix_aligned = vix_close.reindex(common).ffill().bfill()
        btc_ma20    = btc_aligned.rolling(20).mean()

        spy_common  = spy_ratio.index.intersection(common)
        spy_aligned = spy_ratio.reindex(spy_common)

        plt.style.use("dark_background")
        fig = plt.figure(figsize=(11, 10))
        gs = gridspec.GridSpec(4, 1, height_ratios=[3, 1.35, 1.35, 1.15], hspace=0.10)

        # ── Panel 1: BTC + MA20
        ax1 = fig.add_subplot(gs[0])
        ax1.plot(common, btc_aligned, color=_C["btc"], linewidth=1.8, label="BTC-USD", zorder=3)
        ax1.plot(common, btc_ma20,    color=_C["ma"],  linewidth=1.0, linestyle="--", alpha=0.8, label="MA20", zorder=2)
        ax1.fill_between(common, btc_aligned, btc_aligned.min(), alpha=0.08, color=_C["btc"])
        ax1.set_ylabel("BTC-USD", color=_C["btc"], fontsize=9)
        ax1.tick_params(axis="y", colors=_C["btc"], labelsize=8)
        ax1.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        ax1.legend(loc="upper left", fontsize=8, framealpha=0.3)
        ax1.set_title(
            f"Q-Silicon Daily Brief  ·  {datetime.now().strftime('%Y-%m-%d')}",
            color="white", fontsize=10, pad=6
        )
        _remove_spines(ax1)

        # ── Panel 2: VIX with danger zones
        ax2 = fig.add_subplot(gs[1], sharex=ax1)
        vix_vals = vix_aligned.values
        ax2.plot(common, vix_vals, color=_C["vix"], linewidth=1.5, label="VIX")
        ax2.axhspan(30, vix_vals.max() * 1.1, alpha=0.15, color="red",    label="恐慌 >30")
        ax2.axhspan(20, 30,                    alpha=0.08, color="orange", label="警戒 20-30")
        ax2.axhline(20, color="orange", linewidth=0.5, linestyle=":")
        ax2.axhline(30, color="red",    linewidth=0.5, linestyle=":")
        ax2.set_ylabel("VIX", color=_C["vix"], fontsize=9)
        ax2.tick_params(axis="y", colors=_C["vix"], labelsize=8)
        ax2.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        ax2.legend(loc="upper left", fontsize=7, framealpha=0.3)
        _remove_spines(ax2)

        # ── Panel 3: SPY volume ratio (ETF flow proxy)
        ax3 = fig.add_subplot(gs[2], sharex=ax1)
        if len(spy_aligned) > 0:
            colors_bar = [_C["blue"] if r >= 1.0 else _C["red"] for r in spy_aligned.values]
            ax3.bar(spy_common, spy_aligned.values, color=colors_bar, alpha=0.8, width=0.8)
            ax3.axhline(1.0, color="white", linewidth=0.5, linestyle="--", alpha=0.5)
            ax3.set_ylabel("SPY 量比", color=_C["blue"], fontsize=9)
            ax3.tick_params(axis="y", colors=_C["blue"], labelsize=8)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax3.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        ax3.tick_params(axis="x", colors="gray", labelsize=7, rotation=30)
        ax3.legend(["SPY 量比 (藍>1=放量，紅<1=縮量)"], loc="upper left", fontsize=7, framealpha=0.3)
        _remove_spines(ax3)

        # ── Panel 4: BTC funding rate (Binance)
        ax4 = fig.add_subplot(gs[3])
        fund = _fetch_btc_funding_pct_series(limit=120)
        if fund:
            fx, fy = fund
            ax4.plot(fx, fy, color=_C["cyan"], linewidth=1.2, label="Funding % (8h)")
            ax4.axhline(0, color="white", linewidth=0.4, linestyle=":", alpha=0.5)
            ax4.set_ylabel("Funding %", color=_C["cyan"], fontsize=9)
            ax4.tick_params(axis="y", colors=_C["cyan"], labelsize=8)
            ax4.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            ax4.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(fx) // 12)))
            ax4.tick_params(axis="x", colors="gray", labelsize=7, rotation=25)
            ax4.legend(loc="upper left", fontsize=7, framealpha=0.3)
            ax4.set_title("BTC USDT-M 資金費率（Binance 公開 API）", color="white", fontsize=9, pad=4)
        else:
            ax4.text(0.5, 0.5, "Funding 資料暫無法取得", ha="center", va="center", color="gray", fontsize=9)
            ax4.set_axis_off()
        _remove_spines(ax4)

        fig.text(0.5, 0.5, "Q-Silicon Institutional Research",
                 fontsize=13, ha="center", va="center", alpha=0.06, rotation=20)

        fig.savefig(filename, dpi=130, bbox_inches="tight", facecolor="#0E0E0E")
        plt.close(fig)
        logger.info("4-panel quant chart saved: %s", filename)

    except Exception as e:
        logger.warning("visualizer: generate_quant_chart failed — %s", e)


def _fallback_chart(btc, vix, filename: str) -> None:
    """後備：若 SPY 資料缺失，退回原始雙軸圖。"""
    try:
        btc_close = btc["Close"].squeeze() if not btc.empty else None
        vix_close = vix["Close"].squeeze() if not vix.empty else None
        if btc_close is None or vix_close is None:
            return
        common = btc_close.index.intersection(vix_close.index).sort_values()
        if len(common) < 2:
            return
        plt.style.use("dark_background")
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax1.plot(common, btc_close.reindex(common).ffill(), color="lime", linewidth=1.5, label="BTC-USD")
        ax1.set_ylabel("BTC-USD", color="lime")
        ax1.tick_params(axis="y", colors="lime")
        ax1.legend(loc="upper left")
        ax2 = ax1.twinx()
        ax2.plot(common, vix_close.reindex(common).ffill(), color="red", linewidth=1.2, alpha=0.9, label="VIX")
        ax2.set_ylabel("VIX", color="red")
        ax2.tick_params(axis="y", colors="red")
        ax2.legend(loc="upper right")
        fig.text(0.5, 0.5, "Q-Silicon Institutional Research", fontsize=14, ha="center", va="center", alpha=0.15)
        plt.tight_layout()
        fig.savefig(filename, dpi=120, bbox_inches="tight")
        plt.close(fig)
        logger.info("Fallback chart saved: %s", filename)
    except Exception as e:
        logger.warning("_fallback_chart failed — %s", e)
