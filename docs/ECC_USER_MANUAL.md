# Everything Claude Code — 用戶使用手冊

> **版本**: v1.9.0 | **安裝狀態**: 已完成 full profile 安裝

---

## 目錄

1. [什麼是 ECC？](#什麼是-ecc)
2. [已安裝的內容](#已安裝的內容)
3. [核心概念](#核心概念)
4. [Agents（子代理）](#agents子代理)
5. [Commands（斜線指令）](#commands斜線指令)
6. [Skills（技能）](#skills技能)
7. [Rules（規則）](#rules規則)
8. [Hooks（鉤子）](#hooks鉤子)
9. [常用工作流程](#常用工作流程)
10. [Token 優化](#token-優化)
11. [安全掃描 AgentShield](#安全掃描-agentshield)
12. [持續學習系統](#持續學習系統)
13. [針對本專案的建議用法](#針對本專案的建議用法)
14. [疑難排解](#疑難排解)

---

## 什麼是 ECC？

**Everything Claude Code（ECC）** 是一套 Claude Code 效能優化系統，由 Anthropic Hackathon 得獎作品發展而來。它不只是設定檔，而是包含：

- **30 個專業子代理** — 各司其職的 AI 助手
- **135+ 技能定義** — 涵蓋各類開發工作流程
- **60 個斜線指令** — 快速執行常見任務
- **12 種語言規則** — 語言專屬最佳實踐
- **自動化 Hooks** — 觸發式工作流程自動化
- **持續學習系統** — 從每次 session 中提取可重用模式

---

## 已安裝的內容

安裝位置：`~/.claude/`

| 目錄 | 數量 | 說明 |
|------|------|------|
| `~/.claude/agents/` | 30 個 | 專業子代理定義 |
| `~/.claude/commands/` | 60 個 | 斜線指令 |
| `~/.claude/skills/` | 137 個 | 工作流程技能 |
| `~/.claude/rules/` | 12 語言 | 常駐規則 |
| `~/.claude/ecc/install-state.json` | — | 安裝狀態記錄 |

---

## 核心概念

### 層次結構

```
Commands（最快）   → 一行斜線指令，快速啟動 workflow
     ↓
Skills（中層）     → 詳細 workflow 定義，含步驟與規範
     ↓
Agents（最深）     → 獨立子代理，有自己的工具權限與模型
     ↓
Rules（底層）      → 常駐在每次 session 的指導原則
```

### 呼叫方式

- **指令形式**：`/plan "新增用戶驗證功能"`
- **技能形式**：由 Claude 自動依情境呼叫，或用 `/skill-name`
- **代理形式**：Claude 自動委派，或明確說「請用 code-reviewer 代理審查這段程式」

---

## Agents（子代理）

子代理位於 `~/.claude/agents/`，每個代理有專屬工具權限。

### 代理清單與用途

| 代理 | 何時使用 |
|------|----------|
| `planner` | 規劃新功能的實作步驟 |
| `architect` | 設計系統架構、模組邊界 |
| `tdd-guide` | 測試驅動開發輔助 |
| `code-reviewer` | 程式碼品質與安全審查 |
| `security-reviewer` | 漏洞分析、OWASP 檢查 |
| `build-error-resolver` | 解決建置失敗錯誤 |
| `python-reviewer` | Python 專屬代碼審查 |
| `e2e-runner` | Playwright E2E 測試 |
| `refactor-cleaner` | 清理死碼、重構 |
| `doc-updater` | 同步更新文件 |
| `database-reviewer` | 資料庫 schema 與查詢審查 |
| `go-reviewer` / `rust-reviewer` | 各語言專屬審查 |
| `loop-operator` | 自主循環執行任務 |
| `harness-optimizer` | 優化 AI harness 設定 |
| `chief-of-staff` | 溝通分類、草稿撰寫 |
| `pytorch-build-resolver` | PyTorch / CUDA 訓練錯誤 |

### 如何觸發代理

```
# 直接委派
請用 code-reviewer 審查我剛寫的 tools.py

# 使用指令（自動選擇代理）
/code-review

# 明確指定模型
/code-review --model opus
```

---

## Commands（斜線指令）

所有指令位於 `~/.claude/commands/`，在 Claude Code 中輸入 `/` 即可看到清單。

### 最常用指令

#### 開發流程

| 指令 | 說明 |
|------|------|
| `/plan "任務描述"` | 規劃功能實作，生成步驟清單 |
| `/tdd` | 開啟測試驅動開發模式（先寫測試） |
| `/code-review` | 審查目前改動的程式碼 |
| `/build-fix` | 自動修復建置錯誤 |
| `/refactor-clean` | 清理死碼與重構 |
| `/verify` | 執行驗證迴圈（測試 + 靜態分析） |
| `/test-coverage` | 檢查並提升測試覆蓋率 |
| `/update-docs` | 同步更新文件 |

#### 安全與品質

| 指令 | 說明 |
|------|------|
| `/security-scan` | 執行 AgentShield 安全掃描 |
| `/e2e` | 執行 E2E 測試 |
| `/eval` | 評估輸出品質 |
| `/quality-gate` | 執行品質閘門檢查 |

#### 工作管理

| 指令 | 說明 |
|------|------|
| `/checkpoint` | 建立檢查點（可回滾） |
| `/sessions` | 查看 session 歷史 |
| `/save-session` | 儲存目前 session |
| `/resume-session` | 恢復先前 session |
| `/projects` | 管理多個專案 |

#### 多代理編排

| 指令 | 說明 |
|------|------|
| `/orchestrate` | 編排多個代理協作 |
| `/multi-plan` | 多代理並行規劃 |
| `/multi-execute` | 多代理並行執行 |
| `/loop-start` | 啟動自主循環代理 |
| `/loop-status` | 查看循環代理狀態 |

#### 持續學習

| 指令 | 說明 |
|------|------|
| `/learn` | 從目前 session 提取學習 |
| `/instinct-status` | 查看已學習的 instincts |
| `/instinct-export` | 匯出 instincts 分享 |
| `/evolve` | 將 instincts 群聚成 skills |

---

## Skills（技能）

Skills 是詳細的工作流程定義，位於 `~/.claude/skills/`，由 Claude 依情境自動選用，或可明確呼叫。

### 本專案最相關的 Skills

#### Python 開發

| 技能 | 說明 |
|------|------|
| `python-patterns` | Python 最佳實踐與設計模式 |
| `python-testing` | pytest 測試策略 |
| `tdd-workflow` | 紅-綠-重構循環 |
| `verification-loop` | 驗證迴圈（適合 pipeline 測試） |
| `search-first` | 研究優先的開發方式 |

#### AI / LLM 管道

| 技能 | 說明 |
|------|------|
| `cost-aware-llm-pipeline` | LLM 成本感知管道設計 |
| `eval-harness` | 評估框架搭建 |
| `continuous-agent-loop` | 持續代理循環 |
| `agentic-engineering` | Agent 工程模式 |
| `ai-first-engineering` | AI 優先工程原則 |
| `prompt-optimizer` | Prompt 優化 |
| `token-budget-advisor` | Token 預算建議 |

#### 部署與基礎設施

| 技能 | 說明 |
|------|------|
| `deployment-patterns` | 部署模式 |
| `docker-patterns` | Docker 最佳實踐 |
| `database-migrations` | 資料庫遷移策略 |
| `security-review` | 安全審查流程 |

#### 業務內容（投資報告相關）

| 技能 | 說明 |
|------|------|
| `market-research` | 市場研究工作流程 |
| `investor-materials` | 投資人資料撰寫 |
| `deep-research` | 深度研究模式 |

---

## Rules（規則）

Rules 在每次 session 中常駐生效，無需呼叫。位於 `~/.claude/rules/`。

### 已安裝的規則

```
~/.claude/rules/
├── common/          # 通用原則（所有專案適用）
│   ├── agents.md          — 代理使用準則
│   ├── code-review.md     — 程式碼審查標準
│   ├── coding-style.md    — 編碼風格
│   ├── development-workflow.md — 開發工作流程
│   ├── git-workflow.md    — Git 工作流程
│   ├── hooks.md           — Hooks 使用規範
│   ├── patterns.md        — 設計模式
│   ├── performance.md     — 效能最佳化
│   ├── security.md        — 安全準則
│   └── testing.md         — 測試策略
├── python/          # Python 專屬規則
├── typescript/      # TypeScript 專屬規則
├── golang/          # Go 專屬規則
└── ...（其他語言）
```

這些規則會自動影響 Claude 的回答，例如：不加 emoji、測試優先、不靜默吞掉例外等。

---

## Hooks（鉤子）

Hooks 是在特定事件觸發的自動化腳本，已安裝至 `~/.claude/settings.json`。

### Hook 類型

| 類型 | 觸發時機 |
|------|----------|
| `PreToolUse` | 工具執行前（驗證、提醒） |
| `PostToolUse` | 工具完成後（格式化、反饋） |
| `UserPromptSubmit` | 送出訊息時 |
| `Stop` | Claude 完成回應時 |
| `PreCompact` | 上下文壓縮前 |

### 調整 Hook 嚴格程度

```bash
# 設定 profile（minimal / standard / strict）
export ECC_HOOK_PROFILE=standard

# 暫時停用特定 hook
export ECC_DISABLED_HOOKS="pre:bash:tmux-reminder,post:edit:typecheck"
```

---

## 常用工作流程

### 1. 開始新功能

```
/plan "新增 X 功能"
→ Claude 生成詳細步驟清單

/tdd
→ 先寫失敗測試，再實作，最後通過

/code-review
→ 審查實作品質與安全性
```

### 2. 修復 Bug（本專案建議流程）

```
# 先寫能重現 bug 的測試（符合 CLAUDE.md §7 test-first 原則）
/tdd
→ 撰寫失敗測試重現問題

# 修復後驗證
/verify
→ 執行完整驗證迴圈

/code-review
→ 確認修復不引入新問題
```

### 3. 準備上線

```
/security-scan
→ 掃描安全漏洞

/test-coverage
→ 確認覆蓋率達標

/quality-gate
→ 最終品質閘門

/update-docs
→ 同步更新文件
```

### 4. 深度研究（適合本專案的市場研究工作）

```
/orchestrate "研究 [主題] 並生成報告"
→ 多代理並行研究

# 或使用技能
提示 Claude 使用 deep-research skill 研究 [主題]
```

### 5. 優化 LLM 成本

```
提示 Claude 使用 cost-aware-llm-pipeline skill 分析目前管道成本
提示 Claude 使用 token-budget-advisor 建議 token 預算設定
```

---

## Token 優化

在 `~/.claude/settings.json` 加入以下設定（已有部分預設值）：

```json
{
  "model": "sonnet",
  "env": {
    "MAX_THINKING_TOKENS": "10000",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50",
    "CLAUDE_CODE_SUBAGENT_MODEL": "haiku"
  }
}
```

| 設定 | 效果 |
|------|------|
| `model: "sonnet"` | 比 Opus 節省約 60% 成本 |
| `MAX_THINKING_TOKENS: "10000"` | 思考 token 減少約 70% |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE: "50"` | 長 session 品質更好 |
| `CLAUDE_CODE_SUBAGENT_MODEL: "haiku"` | 子代理用較便宜模型 |

**重要**：MCP 保持 10 個以下啟用；工具保持 80 個以下活躍。

切換到 Opus 做深度架構設計：`/model opus`

---

## 安全掃描 AgentShield

不需要安裝，直接使用 npx：

```bash
# 快速掃描（掃描 CLAUDE.md、settings.json、MCP 設定、hooks）
npx ecc-agentshield scan

# 自動修復安全問題
npx ecc-agentshield scan --fix

# 深度分析（3 個 Opus 代理紅隊/藍隊/審計）
npx ecc-agentshield scan --opus --stream

# 從零生成安全設定
npx ecc-agentshield init
```

在 Claude Code 中使用：

```
/security-scan
```

掃描範圍：secrets（14 種模式）、權限設定、hook 注入風險、MCP server 風險、代理設定。

---

## 持續學習系統

ECC 可從每次 session 自動提取模式，建立個人化的 instincts。

```bash
# 查看已學到的 instincts 及信心分數
/instinct-status

# 從目前 session 學習
/learn

# 匯出分享給他人
/instinct-export

# 匯入他人的 instincts
/instinct-import <file>

# 將相關 instincts 群聚成新 skill
/evolve
```

---

## 針對本專案的建議用法

本專案是 **Q-Silicon 機構研究 AI Agent**（Python + CrewAI），以下是最相關的 ECC 用法：

### 1. 修 Bug 時

```
/tdd  ← 先寫失敗測試（符合 CLAUDE.md §7 規範）
修復後執行: python3 -m pytest -m smoke -v
```

### 2. 審查 Gate 邏輯時（report_html_gates.py）

```
請用 python-reviewer 代理審查 report_html_gates.py 的 validate_report 函數
```

### 3. 新增 Tool 時（tools.py）

```
提示 Claude 使用 python-patterns skill 確認 _get_cache/_set_cache 模式一致
```

### 4. 研究 LLM 成本優化

```
提示 Claude 使用 cost-aware-llm-pipeline skill 分析 crew.py 的 LLM 呼叫成本
```

### 5. 安全審查（部署前）

```
/security-scan  ← 掃描 .env 設定、MCP 風險
```

### 6. 建置錯誤

```
/build-fix  ← 自動偵測並修復 Python 建置 / import 錯誤
```

---

## 疑難排解

### 指令找不到

```bash
# 確認版本 >= 2.1.0
claude --version

# 查看已安裝的指令
ls ~/.claude/commands/

# 查看已安裝的代理
ls ~/.claude/agents/
```

### Hooks 產生衝突

```bash
# 暫時停用所有 ECC hooks
export ECC_HOOK_PROFILE=minimal
```

### 重新安裝或更新

```bash
cd /tmp/ecc
git pull
./install.sh --profile full
```

### 查看安裝狀態

```bash
cat ~/.claude/ecc/install-state.json | head -30
```

### 多 MCP 導致 context window 縮減

在 `~/.claude.json` 的 `projects.disabledMcpServers` 中停用非必要的 MCP，保持啟用數 < 10。

---

## 快速參考卡

```
最常用的 10 個指令：

/plan         規劃功能
/tdd          測試驅動開發
/code-review  程式碼審查
/build-fix    修復建置錯誤
/verify       驗證迴圈
/security-scan 安全掃描
/checkpoint   建立回滾點
/update-docs  更新文件
/learn        從 session 學習
/instinct-status 查看已學習模式
```

---

*ECC 源碼：https://github.com/affaan-m/everything-claude-code*
*安裝路徑：`/tmp/ecc`（clone）、`~/.claude/`（已部署）*
