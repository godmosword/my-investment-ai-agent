"""
Q-Silicon Quantitative Backtest Framework
==========================================
用途：驗證我們收集的鏈上指標（DXY、ETF Flow、Risk Score、MVRV Z-Score）
     對 BTC 價格走勢的預測能力，並量化組合信號策略的表現。

執行方式：
    python backtest.py [--days 90] [--capital 10000] [--report html]

依賴：
    - google-cloud-bigquery（已在 requirements.txt）
    - requests（已在 requirements.txt）
    - pandas（已在 requirements.txt）
    - 無需額外 API key（BTC 價格由 CoinGecko 免費 API 取得）
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests
from google.cloud import bigquery

from config import PROJECT_ID, METRICS_TABLE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── 策略參數（可透過 CLI 覆寫）─────────────────────────────────────────────
DEFAULT_DAYS    = 90     # 回測天數
DEFAULT_CAPITAL = 10_000 # 初始資金（USD）

# ── 信號閾值 ──────────────────────────────────────────────────────────────
DXY_BEARISH_THRESHOLD  = 104.0   # DXY > 104  → 美元強勢，BTC 通常承壓
ETF_OUTFLOW_THRESHOLD  = -5.0    # ETF 流出 > 5億 → 拋壓
RISK_OFF_THRESHOLD     = 3.5     # 風險分數 > 3.5 → Risk OFF
MVRV_OVERBOUGHT        = 7.0     # MVRV Z > 7 → 嚴重高估，做空信號
MVRV_OVERSOLD          = 0.0     # MVRV Z < 0 → 底部積累，做多信號
MVRV_HEALTHY_HIGH      = 3.0     # MVRV Z 0~3 → 健康多頭區間

# ── 交易摩擦成本 ──────────────────────────────────────────────────────────
TRANSACTION_COST = 0.001  # 0.1%：含 Taker 手續費 + 滑點，換倉日才扣除

# ── Walk-Forward 參數 ──────────────────────────────────────────────────────
TRAIN_DAYS   = 180   # 每個窗口的訓練天數
TEST_DAYS    = 30    # 每個窗口的測試天數（滾動步長）
OOS_PCT      = 0.20  # 最終 Out-of-Sample 比例（最後 20% 永不參與訓練）


# ══════════════════════════════════════════════════════════════════════════
# 數據獲取
# ══════════════════════════════════════════════════════════════════════════

def fetch_btc_price(days: int) -> pd.DataFrame:
    """從 CoinGecko 免費 API 取 BTC/USD 日收盤價。"""
    url = (
        f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        f"?vs_currency=usd&days={days}&interval=daily"
    )
    logging.info("Fetching BTC price from CoinGecko (%d days)...", days)
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        prices = resp.json().get("prices", [])
        df = pd.DataFrame(prices, columns=["ts_ms", "close"])
        df["date"] = pd.to_datetime(df["ts_ms"], unit="ms").dt.date
        df = df.drop_duplicates("date").set_index("date").sort_index()
        df = df[["close"]].copy()
        logging.info("BTC price fetched: %d rows", len(df))
        return df
    except Exception as e:
        logging.error("CoinGecko fetch failed: %s", e)
        return pd.DataFrame(columns=["close"])


def fetch_indicators(days: int) -> pd.DataFrame:
    """從 BigQuery daily_metrics 取指標數據。"""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("cutoff", "DATE", cutoff)]
    )
    query = f"""
        SELECT
            DATE(timestamp) AS date,
            AVG(dxy)               AS dxy,
            AVG(etf_flow_millions) AS etf_flow,
            AVG(avg_risk_score)    AS risk_score,
            AVG(mvrv_z_score)      AS mvrv_z
        FROM `{METRICS_TABLE}`
        WHERE timestamp >= @cutoff
        GROUP BY date
        ORDER BY date ASC
    """
    logging.info("Fetching indicators from BigQuery (since %s)...", cutoff)
    try:
        client = bigquery.Client(project=PROJECT_ID)
        df = client.query(query, job_config=job_config).to_dataframe()
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df = df.set_index("date").sort_index()
        logging.info("Indicators fetched: %d rows", len(df))
        return df
    except Exception as e:
        logging.error("BigQuery fetch failed: %s", e)
        return pd.DataFrame(columns=["dxy", "etf_flow", "risk_score", "mvrv_z"])


# ══════════════════════════════════════════════════════════════════════════
# 信號生成
# ══════════════════════════════════════════════════════════════════════════

def compute_signals(
    df: pd.DataFrame,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    根據指標計算四個子信號（+1=多, -1=空, 0=中性），
    再加總為複合信號並正規化為 [-1, +1]。

    信號邏輯：
      DXY    > 104      → -1（美元強勢壓制 BTC）
      DXY    ≤ 100      → +1（美元走弱利多 BTC）
      ETF    < -5億     → -1（機構拋壓）
      ETF    > +5億     → +1（機構買入）
      Risk   > 3.5      → -1（Risk OFF 市場）
      Risk   ≤ 2.0      → +1（低風險環境）
      MVRV   > 7        → -1（嚴重高估，賣出）
      MVRV   < 0        → +1（低估，買入）
      MVRV   0~3        → +0.5（健康多頭，輕倉持有）
    """
    df = df.copy()

    # ── DXY 信號 ──────────────────────────────────────────────────
    df["sig_dxy"] = 0.0
    df.loc[df["dxy"] > DXY_BEARISH_THRESHOLD, "sig_dxy"] = -1.0
    df.loc[df["dxy"] <= 100.0, "sig_dxy"] = 1.0

    # ── ETF 資金流信號 ────────────────────────────────────────────
    df["sig_etf"] = 0.0
    df.loc[df["etf_flow"] < ETF_OUTFLOW_THRESHOLD, "sig_etf"] = -1.0
    df.loc[df["etf_flow"] > 5.0, "sig_etf"] = 1.0

    # ── 風險分數信號 ─────────────────────────────────────────────
    df["sig_risk"] = 0.0
    df.loc[df["risk_score"] > RISK_OFF_THRESHOLD, "sig_risk"] = -1.0
    df.loc[df["risk_score"] <= 2.0, "sig_risk"] = 1.0

    # ── MVRV Z-Score 信號 ────────────────────────────────────────
    df["sig_mvrv"] = 0.0
    df.loc[df["mvrv_z"] > MVRV_OVERBOUGHT, "sig_mvrv"] = -1.0
    df.loc[df["mvrv_z"] < MVRV_OVERSOLD,   "sig_mvrv"] = 1.0
    df.loc[(df["mvrv_z"] >= MVRV_OVERSOLD) & (df["mvrv_z"] <= MVRV_HEALTHY_HIGH), "sig_mvrv"] = 0.5

    # ── 複合信號（加權求和，正規化到 [-1, +1]）─────────────────
    w = weights or {"sig_dxy": 0.20, "sig_etf": 0.25, "sig_risk": 0.25, "sig_mvrv": 0.30}
    df["composite"] = sum(df[col] * w.get(col, 0) for col in ["sig_dxy", "sig_etf", "sig_risk", "sig_mvrv"])

    # 最終方向：composite > 0.1 → 多；< -0.1 → 空；否則觀望
    df["position"] = 0.0
    df.loc[df["composite"] > 0.10, "position"] = 1.0
    df.loc[df["composite"] < -0.10, "position"] = -1.0

    return df


# ══════════════════════════════════════════════════════════════════════════
# 回測引擎
# ══════════════════════════════════════════════════════════════════════════

def run_backtest(
    merged: pd.DataFrame,
    initial_capital: float = DEFAULT_CAPITAL,
    transaction_cost: float = TRANSACTION_COST,
) -> tuple[pd.DataFrame, dict]:
    """
    每日收盤重新平衡策略回測：
    - 每天根據前一天收盤計算信號，當天收盤執行（無未來偏差）
    - 做多（+1）: 持有 BTC；做空（-1）: 做空 BTC；觀望（0）: 持有現金
    - 部位發生變化時扣除 0.1% 交易摩擦成本（Taker 手續費 + 滑點）
    """
    df = merged.copy().sort_index()
    df["btc_return"] = df["close"].pct_change()

    # 用前一天信號決定今天倉位（避免 look-ahead bias）
    df["pos_shifted"] = df["position"].shift(1).fillna(0)

    # 換倉偵測：部位與前一期不同即扣一次摩擦成本
    df["pos_change"]  = df["pos_shifted"].diff().abs().fillna(0)
    df["cost"]        = df["pos_change"].clip(upper=1) * transaction_cost

    df["strategy_return"] = df["pos_shifted"] * df["btc_return"] - df["cost"]
    df["bh_return"]       = df["btc_return"]  # Buy & Hold 基準（含摩擦成本則不公平，故不扣）

    df["equity"]    = initial_capital * (1 + df["strategy_return"]).cumprod()
    df["bh_equity"] = initial_capital * (1 + df["bh_return"]).cumprod()

    # ── 績效統計 ──────────────────────────────────────────────────
    total_days = len(df)
    strat_total = (df["equity"].iloc[-1] / initial_capital - 1) * 100
    bh_total    = (df["bh_equity"].iloc[-1] / initial_capital - 1) * 100

    ann_factor = 365 / total_days
    strat_ann  = ((1 + strat_total / 100) ** ann_factor - 1) * 100
    bh_ann     = ((1 + bh_total / 100) ** ann_factor - 1) * 100

    # Sharpe ratio（無風險利率 = 5% / 年，日化）
    rf_daily = 0.05 / 365
    excess   = df["strategy_return"] - rf_daily
    sharpe   = (excess.mean() / excess.std() * math.sqrt(365)) if excess.std() > 0 else 0

    # Max Drawdown
    roll_max  = df["equity"].cummax()
    drawdown  = (df["equity"] - roll_max) / roll_max
    max_dd    = drawdown.min() * 100

    # Win Rate
    trade_days = df[df["pos_shifted"] != 0]
    wins       = (trade_days["strategy_return"] > 0).sum()
    win_rate   = wins / len(trade_days) * 100 if len(trade_days) > 0 else 0

    # 平均持倉比例
    long_pct   = (df["pos_shifted"] == 1).mean() * 100
    short_pct  = (df["pos_shifted"] == -1).mean() * 100
    cash_pct   = (df["pos_shifted"] == 0).mean() * 100
    n_trades   = int((df["pos_change"] > 0).sum())
    total_cost = round(df["cost"].sum() * 100, 3)  # 累積摩擦成本（%）

    stats = {
        "period_days":          total_days,
        "strategy_total_pct":   round(strat_total, 2),
        "bh_total_pct":         round(bh_total, 2),
        "strategy_annual_pct":  round(strat_ann, 2),
        "bh_annual_pct":        round(bh_ann, 2),
        "sharpe_ratio":         round(sharpe, 3),
        "max_drawdown_pct":     round(max_dd, 2),
        "win_rate_pct":         round(win_rate, 2),
        "n_trades":             n_trades,
        "total_friction_cost_pct": total_cost,
        "long_pct":             round(long_pct, 1),
        "short_pct":            round(short_pct, 1),
        "cash_pct":             round(cash_pct, 1),
        "final_equity":         round(df["equity"].iloc[-1], 2),
        "bh_final_equity":      round(df["bh_equity"].iloc[-1], 2),
    }
    return df, stats


# ══════════════════════════════════════════════════════════════════════════
# Walk-Forward + Out-of-Sample 回測
# ══════════════════════════════════════════════════════════════════════════

def run_walk_forward_backtest(
    merged: pd.DataFrame,
    initial_capital: float = DEFAULT_CAPITAL,
) -> tuple[dict, dict, dict]:
    """
    滾動窗口 Walk-Forward 最佳化 + 最後 20% Out-of-Sample 驗證。

    流程：
    1. 保留最後 OOS_PCT（20%）作為 holdout，永不參與訓練
    2. 在剩餘 80% 上滾動：每 TRAIN_DAYS 訓練 → 優化權重 → 下 TEST_DAYS 測試
    3. 最後一組權重用於 OOS 區間，報告 OOS 績效
    4. 回傳 (wf_stats, oos_stats, opt_weights)
    """
    df = merged.copy().sort_index()
    n = len(df)
    oos_start = int(n * (1 - OOS_PCT))
    train_pool = df.iloc[:oos_start]
    oos_pool   = df.iloc[oos_start:]

    if len(train_pool) < TRAIN_DAYS + TEST_DAYS:
        logging.warning(
            "數據不足（需至少 %d 天），跳過 Walk-Forward。請增加 --days 或先執行 backfill。",
            TRAIN_DAYS + TEST_DAYS,
        )
        return {}, {}, {}

    # ── Walk-Forward 滾動窗口 ─────────────────────────────────────────
    wf_returns = []
    last_weights = None
    step = TEST_DAYS
    i = 0
    while i + TRAIN_DAYS + TEST_DAYS <= len(train_pool):
        train_slice = train_pool.iloc[i : i + TRAIN_DAYS]
        test_slice  = train_pool.iloc[i + TRAIN_DAYS : i + TRAIN_DAYS + TEST_DAYS]

        train_df = compute_signals(train_slice)
        opt_res  = optimize_weights(train_df, initial_capital=initial_capital, n_trials=500)
        weights  = opt_res.get("optimal_weights") or {"sig_dxy": 0.25, "sig_etf": 0.25, "sig_risk": 0.25, "sig_mvrv": 0.25}
        last_weights = weights

        test_df = compute_signals(test_slice, weights=weights)
        _, test_stats = run_backtest(test_df, initial_capital=initial_capital)
        # 重建 test 期間的日報酬用於串接
        test_df = test_df.copy()
        test_df["btc_return"] = test_df["close"].pct_change()
        test_df["pos_shifted"] = test_df["position"].shift(1).fillna(0)
        test_df["pos_change"]  = test_df["pos_shifted"].diff().abs().fillna(0)
        test_df["cost"]        = test_df["pos_change"].clip(upper=1) * TRANSACTION_COST
        test_ret = test_df["pos_shifted"] * test_df["btc_return"] - test_df["cost"]
        wf_returns.append(test_ret.dropna())

        i += step

    # 串接所有 WF 測試期報酬
    wf_ret_series = pd.concat(wf_returns) if wf_returns else pd.Series(dtype=float)
    rf_daily = 0.05 / 365
    wf_sharpe = 0.0
    if len(wf_ret_series) > 1 and wf_ret_series.std() > 1e-8:
        wf_sharpe = (wf_ret_series.mean() - rf_daily) / wf_ret_series.std() * math.sqrt(365)
    wf_equity = initial_capital * (1 + wf_ret_series).cumprod()
    wf_total  = (wf_equity.iloc[-1] / initial_capital - 1) * 100 if len(wf_equity) > 0 else 0

    wf_stats = {
        "period_days":        len(wf_ret_series),
        "total_return_pct":   round(wf_total, 2),
        "sharpe_ratio":       round(wf_sharpe, 3),
        "n_windows":          len(wf_returns),
    }

    # ── Out-of-Sample 驗證 ───────────────────────────────────────────
    oos_stats = {}
    if len(oos_pool) >= 5 and last_weights:
        oos_df = compute_signals(oos_pool, weights=last_weights)
        _, oos_stats = run_backtest(oos_df, initial_capital=initial_capital)
        oos_stats["_oos"] = True  # 標記為 OOS

    return wf_stats, oos_stats, (last_weights or {})


# ══════════════════════════════════════════════════════════════════════════
# 權重最佳化（scipy.optimize — 最大化 Sharpe Ratio）
# ══════════════════════════════════════════════════════════════════════════

def optimize_weights(
    merged: pd.DataFrame,
    initial_capital: float = DEFAULT_CAPITAL,
    n_trials: int = 2000,
) -> dict:
    """
    用 Monte Carlo 隨機搜尋 + scipy.optimize.minimize 精修，
    找出令 Sharpe Ratio 最大的四因子權重組合。

    約束條件：所有權重為正且總和為 1（模擬真實配置邏輯）。
    回傳最佳權重與對應績效。
    """
    try:
        from scipy.optimize import minimize
    except ImportError:
        logging.warning("scipy 未安裝，跳過權重最佳化。請執行 pip install scipy。")
        return {}

    factor_cols = ["sig_dxy", "sig_etf", "sig_risk", "sig_mvrv"]
    available = [c for c in factor_cols if c in merged.columns]
    if len(available) < 2:
        logging.warning("可用因子信號不足 2 個，跳過最佳化。")
        return {}

    def _sharpe_from_weights(w: np.ndarray) -> float:
        """給定權重向量，計算對應策略的負 Sharpe（minimize 用）。"""
        df = merged.copy()
        composite = sum(df[col] * wi for col, wi in zip(available, w))
        df["position"] = 0.0
        df.loc[composite > 0.10, "position"] = 1.0
        df.loc[composite < -0.10, "position"] = -1.0
        df["btc_return"]  = df["close"].pct_change()
        pos_shifted       = df["position"].shift(1).fillna(0)
        pos_change        = pos_shifted.diff().abs().fillna(0)
        cost              = pos_change.clip(upper=1) * TRANSACTION_COST
        strat_ret         = pos_shifted * df["btc_return"] - cost
        rf_daily          = 0.05 / 365
        excess            = strat_ret - rf_daily
        if excess.std() < 1e-8:
            return 0.0
        return -(excess.mean() / excess.std() * math.sqrt(365))

    n = len(available)
    constraints = {"type": "eq", "fun": lambda w: w.sum() - 1.0}
    bounds = [(0.05, 0.70)] * n  # 每個因子最少 5%，最多 70%

    # Monte Carlo 找全域最優起點
    best_sharpe = float("inf")
    best_w0     = np.ones(n) / n
    rng         = np.random.default_rng(42)
    for _ in range(n_trials):
        w0 = rng.dirichlet(np.ones(n))
        s  = _sharpe_from_weights(w0)
        if s < best_sharpe:
            best_sharpe = s
            best_w0     = w0

    # 精修
    result = minimize(
        _sharpe_from_weights,
        best_w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 500},
    )

    opt_weights = dict(zip(available, result.x.round(4)))
    opt_sharpe  = round(-result.fun, 3)
    logging.info("最佳化完成：Sharpe=%.3f，權重=%s", opt_sharpe, opt_weights)
    return {"optimal_weights": opt_weights, "optimal_sharpe": opt_sharpe}


# ══════════════════════════════════════════════════════════════════════════
# 特徵工程（Lag / 動量）
# ══════════════════════════════════════════════════════════════════════════

def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """加入 DXY 3 日 MA、MVRV 7 日動量等特徵，供進階策略使用。"""
    out = df.copy()
    if "dxy" in out.columns:
        out["dxy_ma3"] = out["dxy"].rolling(3, min_periods=1).mean()
    if "mvrv_z" in out.columns:
        out["mvrv_momentum_7"] = out["mvrv_z"] - out["mvrv_z"].shift(7)
    return out


# ══════════════════════════════════════════════════════════════════════════
# 績效歸因（單因子策略報酬）
# ══════════════════════════════════════════════════════════════════════════

def performance_attribution(
    merged: pd.DataFrame,
    weights: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    計算各因子若單獨使用時的策略總報酬（%），
    用於評估哪個因子對報酬貢獻最大。
    """
    w = weights or {"sig_dxy": 0.20, "sig_etf": 0.25, "sig_risk": 0.25, "sig_mvrv": 0.30}
    df = merged.copy()
    df["btc_return"] = df["close"].pct_change()
    rf_daily = 0.05 / 365

    contrib = {}
    for col in ["sig_dxy", "sig_etf", "sig_risk", "sig_mvrv"]:
        if col not in df.columns:
            continue
        # 單因子：只用該因子的信號（scaled to [-1,1] 作為 position）
        pos = df[col].fillna(0)
        pos = np.clip(pos, -1, 1)  # 已為 -1/0/0.5/1，不需再 threshold
        pos_shifted = pos.shift(1).fillna(0)
        pos_change  = pos_shifted.diff().abs().fillna(0)
        cost        = pos_change.clip(upper=1) * TRANSACTION_COST
        strat_ret   = pos_shifted * df["btc_return"] - cost
        total_ret   = (1 + strat_ret).prod() - 1
        sharpe      = (strat_ret.mean() - rf_daily) / strat_ret.std() * math.sqrt(365) if strat_ret.std() > 1e-8 else 0
        label       = col.replace("sig_", "").upper()
        contrib[f"{label}_total_pct"] = round(total_ret * 100, 2)
        contrib[f"{label}_sharpe"]    = round(sharpe, 3)
    return contrib


# ══════════════════════════════════════════════════════════════════════════
# 個別因子相關性分析
# ══════════════════════════════════════════════════════════════════════════

def factor_analysis(merged: pd.DataFrame) -> dict[str, float]:
    """計算各因子（DXY/ETF/Risk/MVRV）與次日 BTC 報酬的 Pearson 相關係數。"""
    df = merged.copy()
    df["next_return"] = df["close"].pct_change().shift(-1)
    factors = {
        "DXY vs BTC_next_day":       ("dxy",        "next_return"),
        "ETF_Flow vs BTC_next_day":  ("etf_flow",   "next_return"),
        "Risk_Score vs BTC_next_day":("risk_score",  "next_return"),
        "MVRV_Z vs BTC_next_day":    ("mvrv_z",     "next_return"),
    }
    correlations = {}
    for label, (x_col, y_col) in factors.items():
        if x_col in df.columns and y_col in df.columns:
            valid = df[[x_col, y_col]].dropna()
            if len(valid) > 5:
                correlations[label] = round(valid[x_col].corr(valid[y_col]), 4)
            else:
                correlations[label] = None
    return correlations


# ══════════════════════════════════════════════════════════════════════════
# 報告輸出
# ══════════════════════════════════════════════════════════════════════════

def print_report(
    stats: dict,
    correlations: dict[str, float],
    opt_result: dict | None = None,
    output: str = "console",
    wf_stats: dict | None = None,
    oos_stats: dict | None = None,
    attribution: dict[str, float] | None = None,
) -> None:
    lines = [
        "",
        "═══════════════════════════════════════════════════════",
        "  Q-Silicon Quantitative Backtest Report",
        "═══════════════════════════════════════════════════════",
        f"  回測天數：{stats['period_days']} 天",
        f"  初始資金：${DEFAULT_CAPITAL:,.0f} USD",
        "",
        "── 策略表現 ────────────────────────────────────────",
        f"  總報酬（策略）：{stats['strategy_total_pct']:+.2f}%",
        f"  總報酬（Buy & Hold）：{stats['bh_total_pct']:+.2f}%",
        f"  年化報酬（策略）：{stats['strategy_annual_pct']:+.2f}%",
        f"  年化報酬（Buy & Hold）：{stats['bh_annual_pct']:+.2f}%",
        f"  Sharpe Ratio：{stats['sharpe_ratio']:.3f}",
        f"  最大回撤：{stats['max_drawdown_pct']:.2f}%",
        f"  勝率：{stats['win_rate_pct']:.1f}%",
        f"  期末資產（策略）：${stats['final_equity']:,.2f}",
        f"  期末資產（BH）：  ${stats['bh_final_equity']:,.2f}",
        "",
        "── 交易摩擦成本（0.1% / 次換倉）─────────────────",
        f"  換倉次數：{stats.get('n_trades', 'N/A')} 次",
        f"  累積摩擦成本：{stats.get('total_friction_cost_pct', 'N/A')}%",
        "",
    ]
    if wf_stats:
        lines += [
            "── Walk-Forward 訓練期（滾動優化）────────────────",
            f"  窗口數：{wf_stats.get('n_windows', 'N/A')}",
            f"  總報酬：{wf_stats.get('total_return_pct', 'N/A')}%",
            f"  Sharpe Ratio：{wf_stats.get('sharpe_ratio', 'N/A')}",
            "",
        ]
    if oos_stats and oos_stats.get("_oos"):
        oos_sharpe = oos_stats.get("sharpe_ratio", 0)
        wf_sharpe = wf_stats.get("sharpe_ratio", 0) if wf_stats else 0
        overfit_warn = "  ⚠ 過擬合警訊：OOS Sharpe 遠低於 WF，策略可能不具泛化能力" if (isinstance(oos_sharpe, (int, float)) and isinstance(wf_sharpe, (int, float)) and wf_sharpe - oos_sharpe > 0.5) else ""
        lines += [
            "── Out-of-Sample 驗證（最後 20%，未參與訓練）──────",
            f"  總報酬：{oos_stats.get('strategy_total_pct', 'N/A')}%",
            f"  Sharpe Ratio：{oos_stats.get('sharpe_ratio', 'N/A')}",
            f"  最大回撤：{oos_stats.get('max_drawdown_pct', 'N/A')}%",
            overfit_warn,
            "",
        ]
        oos_stats.pop("_oos", None)
    lines += [
        "── 持倉分佈 ────────────────────────────────────────",
        f"  多頭（持 BTC）：{stats['long_pct']:.1f}%",
        f"  空頭（做空）：  {stats['short_pct']:.1f}%",
        f"  觀望（現金）：  {stats['cash_pct']:.1f}%",
        "",
        "── 因子相關性分析（vs 次日 BTC 報酬）─────────────",
    ]
    for label, corr in correlations.items():
        corr_str = f"{corr:+.4f}" if corr is not None else "數據不足"
        direction = ""
        if corr is not None:
            if abs(corr) >= 0.3:
                direction = "★ 強信號"
            elif abs(corr) >= 0.15:
                direction = "◎ 中度信號"
            else:
                direction = "○ 弱信號"
        lines.append(f"  {label:<35}: {corr_str}  {direction}")

    if attribution:
        lines += [
            "",
            "── 績效歸因（單因子策略若單獨使用時的表現）───────────",
        ]
        factors = sorted({k.replace("_total_pct", "").replace("_sharpe", "") for k in attribution})
        for f in factors:
            pct = attribution.get(f"{f}_total_pct", "N/A")
            shr = attribution.get(f"{f}_sharpe", "N/A")
            pct_str = f"{pct:+.2f}%" if isinstance(pct, (int, float)) else str(pct)
            shr_str = f"{shr:.3f}" if isinstance(shr, (int, float)) else str(shr)
            lines.append(f"  {f:<8} 總報酬：{pct_str:<12} Sharpe：{shr_str}")
        lines.append("")

    opt_lines = []
    if opt_result and opt_result.get("optimal_weights"):
        opt_lines += [
            "",
            "── 最佳權重（scipy 最大化 Sharpe）─────────────────",
            f"  最佳 Sharpe Ratio：{opt_result['optimal_sharpe']:.3f}",
        ]
        for factor, w in opt_result["optimal_weights"].items():
            opt_lines.append(f"  {factor:<12}: {w:.1%}")
        opt_lines.append("  ★ 建議將上方權重更新至 backtest.py 的 weights 字典")

    strat_note = (
        "  Walk-Forward 滾動優化（訓練 180 天 / 測試 30 天）+ 最後 20% OOS 驗證"
        if (wf_stats or oos_stats) else
        "  信號加權：DXY 20% | ETF Flow 25% | Risk Score 25% | MVRV 30%"
    )
    lines += opt_lines + [
        "",
        "── 策略說明 ────────────────────────────────────────",
        strat_note,
        "  複合分數 > 0.10 → 做多；< -0.10 → 做空；其餘觀望",
        "  換倉日扣除 0.1% 交易摩擦成本（Taker Fee + Slippage）",
        "  以前一日信號執行次日操作（無未來偏差）",
        "═══════════════════════════════════════════════════════",
        "",
    ]
    report_text = "\n".join(lines)
    print(report_text)

    if output == "json":
        result = {"stats": stats, "factor_correlations": correlations, "optimization": opt_result}
        if attribution:
            result["performance_attribution"] = attribution
        if wf_stats:
            result["walk_forward"] = wf_stats
        if oos_stats:
            oos_copy = {k: v for k, v in oos_stats.items() if k != "_oos"}
            if oos_copy:
                result["out_of_sample"] = oos_copy
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif output == "html":
        html = "<pre style='font-family:monospace'>" + report_text + "</pre>"
        with open("backtest_report.html", "w", encoding="utf-8") as f:
            f.write(html)
        logging.info("HTML report saved to backtest_report.html")


# ══════════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Q-Silicon BTC Quantitative Backtest")
    parser.add_argument("--days",     type=int,   default=DEFAULT_DAYS,    help="回測天數（預設 90）")
    parser.add_argument("--capital",  type=float, default=DEFAULT_CAPITAL, help="初始資金 USD（預設 10000）")
    parser.add_argument("--report",   type=str,   default="console",       help="輸出格式：console / json / html")
    parser.add_argument("--optimize",      action="store_true", help="執行 scipy 權重最佳化（需較長時間）")
    parser.add_argument("--walk-forward",  action="store_true", help="Walk-Forward 滾動優化 + 最後 20% Out-of-Sample 驗證")
    args = parser.parse_args()

    # 1. 取 BTC 價格
    df_price = fetch_btc_price(args.days)
    if df_price.empty:
        logging.error("無法取得 BTC 價格，終止回測。")
        sys.exit(1)

    # 2. 取指標數據
    df_ind = fetch_indicators(args.days)
    if df_ind.empty:
        logging.warning(
            "BigQuery 無歷史指標數據，僅以 BTC Buy & Hold 作為輸出。\n"
            "請先執行 backfill_data.py 補入歷史數據，或等待戰報寫入後再回測。"
        )
        df_price["position"] = 1.0
        df_price["dxy"] = float("nan")
        df_price["etf_flow"] = float("nan")
        df_price["risk_score"] = float("nan")
        df_price["mvrv_z"] = float("nan")
        merged = df_price.copy()
    else:
        # 3. 對齊日期
        merged = df_price.join(df_ind, how="inner")
        if merged.empty:
            logging.error("BTC 價格與 BigQuery 指標無法對齊日期，回測中止。")
            sys.exit(1)

    # 4. 計算信號
    merged = compute_signals(merged)

    # 5. 執行回測（Walk-Forward 或標準模式）
    wf_stats, oos_stats, opt_weights = {}, {}, {}
    if args.walk_forward:
        logging.info("執行 Walk-Forward 滾動優化 + Out-of-Sample 驗證...")
        wf_stats, oos_stats, opt_weights = run_walk_forward_backtest(merged, initial_capital=args.capital)
        # 標準回測仍用於報告基底（持倉分佈等），以全期 default 權重
        result_df, stats = run_backtest(merged, initial_capital=args.capital)
        if oos_stats and oos_stats.get("_oos"):
            stats["_oos_override"] = True  # 標記：報告中 OOS 區塊會覆蓋部分說明
    else:
        result_df, stats = run_backtest(merged, initial_capital=args.capital)

    # 6. 因子相關性
    correlations = factor_analysis(merged)

    # 6b. 績效歸因（單因子策略報酬）
    weights_for_attr = opt_weights if opt_weights else {"sig_dxy": 0.20, "sig_etf": 0.25, "sig_risk": 0.25, "sig_mvrv": 0.30}
    attribution = performance_attribution(merged, weights=weights_for_attr)

    # 7. 權重最佳化（可選，非 WF 模式時）
    opt_result = opt_weights if opt_weights else {}
    if args.optimize and not args.walk_forward:
        logging.info("開始權重最佳化（Monte Carlo 2000 次 + SLSQP 精修）...")
        opt_result = optimize_weights(merged, initial_capital=args.capital)

    # 8. 輸出報告
    print_report(
        stats, correlations,
        opt_result=opt_result if opt_result else None,
        output=args.report,
        wf_stats=wf_stats if wf_stats else None,
        oos_stats=oos_stats if oos_stats else None,
        attribution=attribution,
    )


if __name__ == "__main__":
    main()
