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

# Restricted-egress opt-in: RESTRICTED_EGRESS=1 adds the filtering egress broker
# so owner-approved cloud endpoints can be reached (the app still has no direct
# internet route). Default (unset) stays fully sealed.
COMPOSE_FILES=(-f docker-compose.yml)
if [[ "${RESTRICTED_EGRESS:-0}" == "1" ]]; then
  COMPOSE_FILES+=(-f docker-compose.egress.yml)
  echo "Restricted egress ON — the app reaches ONLY hosts you approve in Settings → Egress, via the broker."
else
  echo "Building and starting Precepta (this is locked off from the internet)…"
fi
docker compose "${COMPOSE_FILES[@]}" up -d --build

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
