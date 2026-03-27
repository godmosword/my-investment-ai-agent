# `tools.py` 模組化計畫（BL-03）

目標：將單一大檔依 **資料域** 拆分，根目錄保留薄封裝 `tools.py`（或 `tools/__init__.py`）re-export Crew 註冊名稱不變，避免循環 import。

## 建議目錄

```
tools/
  __init__.py      # 公開 API；from tools.foo import bar 相容層
  _cache.py        # _get_cache / _set_cache 共用
  _http.py         # Session、重試
  crypto_*.py      # CoinGlass、CryptoPanic、鏈上
  macro_*.py       # FRED、情緒、VIX 等
  search_*.py      # Apify、NewsAPI、Tavily
  quant_*.py       # 回測／ML 相關工具
```

## 遷移步驟（建議順序）

1. 抽出 **`_cache` / `_http`**，`tools.py` 改為 import 轉發，跑全測試。（**進行中**：[`tools_cache_http.py`](../tools_cache_http.py)）  
2. 依 **import 圖** 將無上層依賴的葉節點先搬（例如單一 REST 工具）。  
3. 每搬一組：**`pytest -m smoke`** + 管線乾跑（`SKIP_TELEGRAM=1 SKIP_BIGQUERY=1`）。  
4. 最後刪減舊 `tools.py` 內文，僅留 re-export。

## 非目標

- 不改工具對外的 **字串契約**（`[DATA_MISSING:…]` 等）。  
- 不在同一 PR 內改商業邏輯；僅搬移與 import 整理。
