#!/usr/bin/env bash
# Preflight check — tells you in plain words what's missing before you start.
cd "$(dirname "$0")"
ok=1
check() {  # name  test-cmd  fix-hint
  if eval "$2" >/dev/null 2>&1; then
    echo "  ✓ $1"
  else
    echo "  ✗ $1 — $3"
    ok=0
  fi
}

echo "Precepta preflight:"
check "Docker is installed"        "command -v docker"          "install Docker Desktop or Docker Engine"
check "Docker is running"          "docker info"                "start Docker, then re-run"
check "docker compose is available" "docker compose version"    "update Docker to a version that includes 'compose'"
check "Port 8000 is free"          "! (command -v lsof >/dev/null && lsof -i :8000 -sTCP:LISTEN)" "stop whatever is using port 8000 (or change the app port mapping)"
check "deploy/.env exists"         "test -f .env"               "run: cp deploy/.env.example deploy/.env  and edit ORG_NAME / ADMIN_EMAIL"

echo
if [[ "$ok" == "1" ]]; then
  echo "All good — run ./deploy/up.sh"
else
  echo "Fix the ✗ items above, then run ./deploy/up.sh"
  exit 1
fi
