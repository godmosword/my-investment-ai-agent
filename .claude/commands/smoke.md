---
description: 快速冒煙測試：ruff lint + pytest smoke markers，CI 前先跑確認沒有明顯錯誤
---

## Smoke Check

執行以下兩個指令，回報結果：

```
!`python3 -m ruff check . 2>&1 | head -30`
```

```
!`python3 -m pytest -m smoke -q 2>&1 | tail -20`
```

如果有失敗，列出具體錯誤並分析根因。如果全部通過，回報「✅ Smoke 通過，可以 push/PR」。
