# 商業化下一步（BL-10）

策略與假設見 [`COMMERCE_PLAYBOOK.md`](COMMERCE_PLAYBOOK.md)。本檔為 **實作前檢查清單**（尚未寫程式）。

## Phase 0 — 決策

- [ ] 付費對象：B2C 訂閱 vs B2B API。  
- [ ] 身分：Email magic link vs OAuth（Google）vs 僅 API key。  
- [ ] 資料邊界：哪些 BQ 資料集可經 API 暴露（最小權限 SA）。

## Phase 1 — Auth

- [ ] 使用者儲存（自建 vs Supabase/Clerk）。  
- [ ] FastAPI 中介層：JWT 或 session；與現有 `api.py` 路由掛鉤。

## Phase 2 — 付費

- [ ] Stripe Product/Price 與 webhook（`customer.subscription.*`）。  
- [ ] 訂閱狀態與 API rate limit 對齊。

## Phase 3 — 上線

- [ ] 稽核日誌、退款流程、ToS/Privacy 連結。  
- [ ] 與 `DEPLOY_RUNBOOK.md` 對齊的 production secrets。

完成任一 phase 後請更新 `TODOS.md` **BL-10** 與 `CHANGELOG.md`。
