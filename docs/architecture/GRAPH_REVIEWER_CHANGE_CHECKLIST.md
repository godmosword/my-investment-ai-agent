# Graph／Reviewer 變更檢查清單

變更 `graph/`（含 `graph_nodes.py`、`graph/graph.py` 等）或 Reviewer 相關邏輯時，**不得**繞過戰報出口契約。

## 必跑（本地或 CI）

```bash
python3 -m pytest test_reviewer_loop.py -q
bash scripts/verify_graph_gate.sh
```

`scripts/verify_graph_gate.sh` 會執行 `test_reviewer_loop`；若專案另有 `pytest -m smoke`，一併納入 release 前流程。

## 紅線（對齊 `REVIEWER_LOOP_DESIGN.md`、`.cursorrules`）

1. **Telegram HTML**：戰報仍須通過 `validate_report`／`report_html_gates`；Reviewer 僅輔助，**不取代** Gate。
2. **數據**：客觀價格／指標不得由 LLM 自行推算；與既有無菌管線一致。
3. **擴充 `schemas` 或 Reviewer state**：同步更新設計稿與對應測試。

## 參考

- [`REVIEWER_LOOP_DESIGN.md`](REVIEWER_LOOP_DESIGN.md)
- [`Terminal_Master_Plan.md`](Terminal_Master_Plan.md) 風險與執行順序
