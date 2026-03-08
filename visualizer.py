"""圖表生成模組：3 Panel BTC 量化儀表板，供戰報 Telegram 發送使用。"""
import logging
from datetime import datetime

import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
import numpy as np

logger = logging.getLogger(__name__)


def generate_quant_chart(filename: str = "daily_chart.png") -> None:
    """
    3 Panel 量化圖表：
    Panel 1 (上): BTC-USD 收盤價 + 20日均線
    Panel 2 (中): VIX 恐慌指數（帶危險區上色）
    Panel 3 (下): SPY 成交額 vs 5日均值比率（ETF 資金流代理）
    """
    try:
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
        fig = plt.figure(figsize=(11, 8))
        gs  = gridspec.GridSpec(3, 1, height_ratios=[3, 1.5, 1.5], hspace=0.08)

        # ── Panel 1: BTC + MA20
        ax1 = fig.add_subplot(gs[0])
        ax1.plot(common, btc_aligned, color="#00FF88", linewidth=1.8, label="BTC-USD", zorder=3)
        ax1.plot(common, btc_ma20,    color="#FFD700", linewidth=1.0, linestyle="--", alpha=0.8, label="MA20", zorder=2)
        ax1.fill_between(common, btc_aligned, btc_aligned.min(), alpha=0.08, color="#00FF88")
        ax1.set_ylabel("BTC-USD", color="#00FF88", fontsize=9)
        ax1.tick_params(axis="y", colors="#00FF88", labelsize=8)
        ax1.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        ax1.legend(loc="upper left", fontsize=8, framealpha=0.3)
        ax1.set_title(
            f"Q-Silicon Daily Brief  ·  {datetime.now().strftime('%Y-%m-%d')}",
            color="white", fontsize=10, pad=6
        )
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)

        # ── Panel 2: VIX with danger zones
        ax2 = fig.add_subplot(gs[1], sharex=ax1)
        vix_vals = vix_aligned.values
        ax2.plot(common, vix_vals, color="#FF4444", linewidth=1.5, label="VIX")
        ax2.axhspan(30, vix_vals.max() * 1.1, alpha=0.15, color="red",    label="恐慌 >30")
        ax2.axhspan(20, 30,                    alpha=0.08, color="orange", label="警戒 20-30")
        ax2.axhline(20, color="orange", linewidth=0.5, linestyle=":")
        ax2.axhline(30, color="red",    linewidth=0.5, linestyle=":")
        ax2.set_ylabel("VIX", color="#FF4444", fontsize=9)
        ax2.tick_params(axis="y", colors="#FF4444", labelsize=8)
        ax2.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        ax2.legend(loc="upper left", fontsize=7, framealpha=0.3)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)

        # ── Panel 3: SPY volume ratio (ETF flow proxy)
        ax3 = fig.add_subplot(gs[2], sharex=ax1)
        if len(spy_aligned) > 0:
            colors_bar = ["#00BFFF" if r >= 1.0 else "#FF6666" for r in spy_aligned.values]
            ax3.bar(spy_common, spy_aligned.values, color=colors_bar, alpha=0.8, width=0.8)
            ax3.axhline(1.0, color="white", linewidth=0.5, linestyle="--", alpha=0.5)
            ax3.set_ylabel("SPY 量比", color="#00BFFF", fontsize=9)
            ax3.tick_params(axis="y", colors="#00BFFF", labelsize=8)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax3.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        ax3.tick_params(axis="x", colors="gray", labelsize=7, rotation=30)
        ax3.legend(["SPY 量比 (藍>1=放量，紅<1=縮量)"], loc="upper left", fontsize=7, framealpha=0.3)
        ax3.spines["top"].set_visible(False)
        ax3.spines["right"].set_visible(False)

        fig.text(0.5, 0.5, "Q-Silicon Institutional Research",
                 fontsize=13, ha="center", va="center", alpha=0.06, rotation=20)

        fig.savefig(filename, dpi=130, bbox_inches="tight", facecolor="#0E0E0E")
        plt.close(fig)
        logger.info("3-panel quant chart saved: %s", filename)

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
