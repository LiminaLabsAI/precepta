#!/usr/bin/env bash
# preceptaai control plane — local run story (Phase 0).
#   ./run.sh            → start the API on http://127.0.0.1:8000
#   ./run.sh test       → run the phase test suite
set -euo pipefail
cd "$(dirname "$0")"

# Load local config/secrets (OIDC creds, backend endpoints, …) from .env if present.
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Creating virtualenv…"
  python3 -m venv .venv
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r requirements.txt
fi

case "${1:-serve}" in
  test)
    exec "$PY" -m pytest -q
    ;;
  reset)
    exec "$PY" -c "from app.admin_ops import reset_activity; import json; print('clean slate — cleared:', json.dumps(reset_activity()))"
    ;;
  serve)
    echo "preceptaai → http://127.0.0.1:8000  (UI: /, health: /health, docs: /docs)"
    exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    ;;
  *)
    echo "usage: ./run.sh [serve|test|reset]"; exit 1;;
esac
