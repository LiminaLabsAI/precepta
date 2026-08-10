# Precepta — sovereign self-host app image (Phase 14).
# Single-node pilot: the FastAPI control plane + the self-contained Console.
# The DB and secrets live on a mounted volume (/data); models are served by a
# separate in-boundary Ollama service (see docker-compose.yml). No core change.
FROM python:3.14-slim

# Small, reproducible layer for deps.
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code + the single-file Console + config.
COPY app/ ./app/
COPY web/ ./web/
COPY config.toml ./config.toml

# Persisted state lives on a volume, owned by the non-root runtime user.
RUN useradd --create-home --uid 10001 precepta \
    && mkdir -p /data \
    && chown -R precepta:precepta /app /data
USER precepta

# State + bind: DB on the volume; serve on all interfaces inside the container
# (the compose network — NOT the public internet — decides who can reach it).
ENV PRECEPTA_DB=/data/preceptaai.db \
    PRECEPTA_HOST=0.0.0.0 \
    PRECEPTA_PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Lightweight healthcheck against the app's own /health.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
