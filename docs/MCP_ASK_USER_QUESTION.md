# AskUserQuestion／AUQ（MCP）安裝說明

`plan-eng-review` 等技能裡的 **AskUserQuestion** 在 **Claude Code** 內建；在 **Cursor** 裡需透過 **MCP** 掛上類似能力。社群實作以 **[auq-mcp-server](https://www.npmjs.com/package/auq-mcp-server)**（Ask User Questions）最常用，工具名通常含 `ask`／`question`，與 Claude Code 的 `AskUserQuestion` 用途相同：**在流程中暫停、用選項收集你的決策**。

---

## 你實際會得到什麼

| 環境 | 行為 |
|------|------|
| **Claude Code** | 內建 `AskUserQuestion`；或用下方 MCP 覆蓋／補強。 |
| **Cursor** | 在 **Cursor Settings → MCP** 新增 server 後，Agent 才可能呼叫對應 MCP tool（名稱依 Cursor 顯示為準）。 |
| **AUQ** | MCP 發問後，需在**另一個終端**執行 **`auq`** 開 TUI 作答（見官方 README）；不是只在 Chat 裡打字。 |

---

## 方式 A：Cursor 一鍵（官方 deeplink）

在瀏覽器開啟（會嘗試喚起 Cursor 寫入 MCP）：

- [Install ask-user-questions MCP（Cursor）](https://cursor.com/en-US/install-mcp?name=ask-user-questions&config=eyJlbnYiOnt9LCJjb21tYW5kIjoibnB4IC15IGF1cS1tY3Atc2VydmVyIHNlcnZlciJ9)

若無法開啟，改用手動（方式 B）。

---

## 方式 B：Cursor 手動新增 MCP

1. 開啟 **Cursor Settings → Features → MCP**（或 **Models / MCP** 依版本而定）。
2. **Add new MCP server**，填入約略如下（以 `npx` 為例，免全域安裝）：

| 欄位 | 建議值 |
|------|--------|
| Name | `ask-user-questions` |
| Command | `npx` |
| Args | `-y` `auq-mcp-server` `server` |

3. 儲存後**重啟 Cursor** 或重新載入 MCP。
4. 在專案外另開終端，安裝並常駐 **AUQ TUI**（發問時才能答）：

```bash
npm install -g auq-mcp-server
# 之後當 Agent 透過 MCP 丟問題過來時：
auq
```

（官方推薦也可用 **Bun**：`bun add -g auq-mcp-server`，渲染較完整。）

---

## 方式 C：Claude Code（專案或全域）

```bash
claude mcp add --transport stdio ask-user-questions -- npx -y auq-mcp-server server
```

或於專案根目錄建立 `.mcp.json`（與 Claude Code 文件一致）：

```json
{
  "mcpServers": {
    "ask-user-questions": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "auq-mcp-server", "server"]
    }
  }
}
```

驗證：在 Claude Code 輸入 `/mcp` 查看 server 是否 online。

---

## 與本 repo 的 `plan-eng-review` 對齊

- 技能要求 **「每議題一次 AskUserQuestion」**：掛上 MCP 後，應請 Agent **實際呼叫 MCP tool** 出選項，而不是只在對話框貼 A/B/C 文字（否則與技能「使用者必須在 UI 選」的意圖不一致）。
- 若 Cursor 未載入 MCP，助理只能**用文字列出選項**請你回覆「選 A/B/C」——功能等價，但就不是工具層的 AskUserQuestion。

---

## 疑難排解

| 現象 | 處理 |
|------|------|
| Agent 說沒有 AskUserQuestion | 確認 MCP 已啟用、server 綠燈、專案已重開。 |
| 工具卡住逾時 | AUQ README 建議拉長 MCP tool timeout；Cursor 若強制短逾時可改走 **Agent Skills** 或本機 `auq`。 |
| 不想用獨立 TUI | 可繼續用 **Chat 內回覆 A/B/C**；不必強裝 MCP。 |

---

## 參考

- npm：[auq-mcp-server](https://www.npmjs.com/package/auq-mcp-server)
- GitHub：[ask-user-questions-mcp](https://github.com/paulp-o/ask-user-questions-mcp)
- FastMCP skill（Claude 網頁上傳用）：[ask-user-question](https://fastmcp.me/Skills/Details/843/ask-user-question)
