# Precepta licensing/onboarding service — the VENDOR control server (NOT the
# sovereign self-host image). Small FastAPI app + SQLite on a writable disk.
# Build context is the repo root: docker build -f licensing/Dockerfile .
FROM python:3.14-slim

WORKDIR /app
COPY licensing/requirements.txt ./licensing/requirements.txt
RUN pip install --no-cache-dir -r licensing/requirements.txt

COPY licensing/ ./licensing/

# State (SQLite) lives on a mounted disk, owned by the non-root runtime user.
RUN useradd --create-home --uid 10001 precepta \
    && mkdir -p /data && chown -R precepta:precepta /app /data
USER precepta

ENV LICENSE_DB=/data/licensing.db \
    PYTHONUNBUFFERED=1
EXPOSE 8099

# Bind $PORT when a managed host (Render/Railway) injects one, else 8099.
CMD ["sh", "-c", "exec python -m uvicorn licensing.service:app --host 0.0.0.0 --port ${PORT:-8099}"]
