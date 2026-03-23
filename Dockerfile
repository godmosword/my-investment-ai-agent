FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Store HuggingFace/sentence-transformers cache in /app/.cache so it is
# accessible to appuser after the chown step below.
ENV HF_HOME=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pre-download the SBERT model at build time so Cloud Run containers never
# need outbound HuggingFace access at runtime.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" \
    || echo "WARN: SBERT model pre-download failed — semantic dedup will be skipped at runtime."
COPY . .
RUN useradd --create-home --shell /bin/false appuser && chown -R appuser /app
USER appuser
CMD ["python", "main.py"]