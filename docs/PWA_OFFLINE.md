# PWA 離線行為（保守策略）

War Room PWA 使用 **InjectManifest** Service Worker：`workbox-precaching` 快取 **build 產物**（JS/CSS/HTML 等）；並加上**保守**的 **runtimeCaching**（見 `data-verification-ui/src/service-worker.js`）。

## 設計原則

1. **`/api/*` 永不進快取**：一律 **`NetworkOnly`**，避免離線時展示過期的行情／報告／訂閱狀態。
2. **HTML 導覽**：**`NetworkFirst`**（逾時約 10s 後改走快取）。若先前成功載入過同一頁，離線時**可能**看到上次頁面殼；**資料仍仰賴 API**，列表／詳情會失敗或顯示錯誤。
3. **同源 script/style/worker**：同樣 **NetworkFirst**，失敗時才回退快取。

## 「最後同步」建議（UI）

若要在 UI 標示資料新鮮度，請以 **API 回應**中的 **`as_of`／`report_date`** 為準（而非 Service Worker 快取時間）。離線時應提示網路不可用，並保留最後一次成功載入的時間戳（若有）。

## 本地開發

`vite` dev server 下若未啟用 SW，以上行為以瀏覽器實際註冊的 SW 為準；正式環境請以 **`npm run build`** 後預覽驗證。
