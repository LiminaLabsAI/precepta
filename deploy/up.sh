#!/usr/bin/env bash
# One command to run Precepta inside your network (egress-locked).
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created deploy/.env from the template."
  echo "  → Open deploy/.env, set ORG_NAME and ADMIN_EMAIL, then run ./deploy/up.sh again."
  exit 0
fi

echo "Building and starting Precepta (this is locked off from the internet)…"
docker compose up -d --build

echo "Loading the AI models into your machine (first run pulls them — a few minutes)…"
code=""
for _ in $(seq 1 80); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health 2>/dev/null || true)"
  [[ "$code" == "200" ]] && break
  sleep 3
done

echo
if [[ "$code" == "200" ]]; then
  echo "✓ Precepta is running → http://127.0.0.1:8000/console"
  echo "  Sign in, then open Deployment to see live status and generate the zero-egress attestation."
else
  echo "⚠ The app hasn't reported healthy yet. Check logs with:"
  echo "    docker compose -f deploy/docker-compose.yml logs -f app"
fi
