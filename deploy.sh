#!/bin/bash
# 本腳本僅推送到 GitHub，實際部署由 .github/workflows/deploy.yml 執行。
# Cloud Run Job 的環境變數來自 GCP Secret Manager，請確保已建立 APIFY_API_TOKEN 等 secret。

git add .
git commit -m "auto deploy update"
git push
echo "✅ 已經成功推送到 GitHub，請等待 GCP 部署！"

