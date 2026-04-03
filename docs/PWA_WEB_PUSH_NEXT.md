# PWA Web Push 持久化（Pri 4 — 下一步勾選）

對齊 TODOS Direction 1A：**不阻塞日報主線**；與 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt) `WEB_PUSH_ENABLED` 預留一致。

## 建議實作切片

1. **Service Worker**：註冊、`push` 事件、離線快取策略（僅靜態資產，避免快取敏感 API）。
2. **訂閱持久化**：`POST /api/push/subscribe` 將 `endpoint`+`keys` 存 Redis／DB（與使用者身分策略一致）。
3. **隱私與合規**：訂閱列表最小化、可撤銷、與 Telegram 推播分開同意。

## 修訂紀錄

- **2026-04-04**：初版 checklist（承接演進計畫階段三）。
