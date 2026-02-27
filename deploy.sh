#!/bin/bash

git add .
git commit -m "auto deploy update"
git push
echo "✅ 已經成功推送到 GitHub，請等待 GCP 部署！"

