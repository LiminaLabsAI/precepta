#!/usr/bin/env bash
# Load realistic sample policies + API keys into the running deployment, so you
# have something real to demonstrate. Idempotent — safe to run more than once.
set -euo pipefail
cd "$(dirname "$0")"

echo "Seeding demo policies + keys into the running Precepta…"
docker compose -f docker-compose.yml exec -T app python -m app.demo_seed

echo
echo "Open http://127.0.0.1:8000/console → Policies and Keys & budgets to see them."
