#!/bin/bash
# 本腳本僅推送到 GitHub，實際部署由 .github/workflows/deploy.yml 執行。
# Cloud Run Job 的環境變數來自 GCP Secret Manager；deploy.yml 另含 NEWSAPI_KEY、GNEWS_API_KEY、FMP_API_KEY、RAPIDAPI_KEY 等，請先於 Console 建立同名 secret 並授權 runtime SA 讀取。

git add .
git commit -m "auto deploy update"
git push
echo "✅ 已經成功推送到 GitHub，請等待 GCP 部署！"

