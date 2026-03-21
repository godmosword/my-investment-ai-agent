# gstack 使用說明（本專案）

## 1) gstack 是什麼

`gstack` 在這裡是 **Claude/Cursor 的技能集合（skills）**，不是一般終端 CLI。  
也就是說，主要使用方式是對話中的 slash 指令，例如：

- `/browse`
- `/review`
- `/plan-ceo-review`
- `/plan-eng-review`
- `/ship`
- `/retro`

## 2) 安裝（本機）

```bash
git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack
./setup
```

## 3) 在哪裡使用

請在 **Cursor/Claude 對話框** 使用，不是在 terminal 輸入 `gstack --version`。  
正確範例：

- 在聊天輸入：`/browse https://example.com`
- 在聊天輸入：`/review`

## 4) 快速驗證是否可用

安裝成功通常可看到：

- `~/.claude/skills/` 下有 symlink（如 `browse`, `review`, `ship`）
- 對話框輸入 `/browse` 不會出現「找不到 skill」

> 注意：`command -v gstack` 顯示找不到，通常不代表安裝失敗。  
> gstack 預設不會把指令註冊到 PATH。

## 5) 失敗排查

若 slash skills 無法觸發：

```bash
cd ~/.claude/skills/gstack
./setup
```

若仍不行：

1. 重新開啟 Cursor 視窗
2. 確認 `~/.claude/skills/` 有 `browse` 等連結
3. 確認 `~/.claude/skills/gstack/browse/dist/browse` 存在

## 6) 本專案建議用法

- 網頁相關操作優先使用 `/browse`
- PR 合併前可先用 `/review` 做結構檢查
- 需求不清時先 `/plan-eng-review` 或 `/plan-ceo-review`

