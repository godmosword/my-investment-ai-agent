"""圖表生成模組：BTC–VIX 雙軸量化圖，供戰報 Telegram 發送使用。"""
import logging

import yfinance as yf
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def generate_quant_chart(filename: str = "daily_chart.png") -> None:
    """
    使用 yfinance 抓取過去 60 天 BTC-USD 與 ^VIX 收盤價，
    繪製雙 Y 軸圖（左：BTC 綠線，右：VIX 紅線），
    背景中央加上半透明浮水印，儲存至 filename 後關閉圖表釋放記憶體。
    """
    try:
        btc = yf.download("BTC-USD", period="60d", interval="1d", progress=False, auto_adjust=True)
        vix = yf.download("^VIX", period="60d", interval="1d", progress=False, auto_adjust=True)
        if btc.empty or vix.empty:
            logger.warning("visualizer: BTC 或 VIX 資料為空，跳過圖表生成。")
            return
        btc_close = btc["Close"] if "Close" in btc.columns else btc.iloc[:, 0]
        vix_close = vix["Close"] if "Close" in vix.columns else vix.iloc[:, 0]
        # 對齊日期（取交集）
        common = btc_close.index.intersection(vix_close.index).sort_values()
        if len(common) < 2:
            logger.warning("visualizer: 共同交易日不足，跳過圖表生成。")
            return

        plt.style.use("dark_background")
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax1.plot(common, btc_close.reindex(common).ffill().bfill(), color="lime", linewidth=1.5, label="BTC-USD")
        ax1.set_ylabel("BTC-USD", color="lime")
        ax1.tick_params(axis="y", colors="lime")
        ax1.legend(loc="upper left")

        ax2 = ax1.twinx()
        ax2.plot(common, vix_close.reindex(common).ffill().bfill(), color="red", linewidth=1.2, alpha=0.9, label="VIX")
        ax2.set_ylabel("VIX", color="red")
        ax2.tick_params(axis="y", colors="red")
        ax2.legend(loc="upper right")

        fig.text(0.5, 0.5, "Q-Silicon Institutional Research", fontsize=14, ha="center", va="center", alpha=0.15)
        plt.tight_layout()
        fig.savefig(filename, dpi=120, bbox_inches="tight")
        plt.close(fig)
        logger.info("Quant chart saved: %s", filename)
    except Exception as e:
        logger.warning("visualizer: generate_quant_chart failed — %s", e)
