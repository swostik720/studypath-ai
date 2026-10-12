FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/hf

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

COPY app ./app
COPY corpus ./corpus

# Non-root user; /models holds the downloaded embedding model (mounted as a volume in compose).
RUN useradd --create-home --uid 1000 appuser && mkdir -p /models/hf && chown -R appuser /models
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
