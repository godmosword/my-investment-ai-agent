# 採用 2026 穩定的 Python 3.11 Slim 版本
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 環境變數優化：不生成 .pyc，且讓 stdout 即時輸出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 複製依賴清單並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案代碼
COPY . .

# 執行主程式 (假設你的入口文件為 main.py)
CMD ["python", "main.py"]
