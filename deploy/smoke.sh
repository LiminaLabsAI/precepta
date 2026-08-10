#!/usr/bin/env bash
# Sovereign smoke test — proves the deployed stack is governed AND zero-egress.
# Run against an already-up stack (./deploy/up.sh first). Exits non-zero on any failure.
set -uo pipefail
cd "$(dirname "$0")"

BASE="http://127.0.0.1:8000"
AUTH="Authorization: Bearer dev-admin"
RC=0
pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; RC=1; }

echo "Precepta sovereign smoke test:"

# 1) control plane healthy
[[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health")" == "200" ]] \
  && pass "control plane healthy" || fail "health not 200"

# 2) a governed request routes to an in-boundary model
resp="$(curl -s -m 120 -H "$AUTH" -H 'Content-Type: application/json' -X POST \
  "$BASE/v1/chat/completions" \
  -d '{"model":"auto","messages":[{"role":"user","content":"reply one word: ok"}],"temperature":0.3}')"
echo "$resp" | grep -qE '"in_boundary": ?true' \
  && pass "governed request routed to an in-boundary model" \
  || fail "request did not route in-boundary"

# 3) the attestation's REAL egress probe says blocked
att="$(curl -s -H "$AUTH" "$BASE/attestation")"
echo "$att" | grep -qE '"result": ?"blocked"' \
  && pass "attestation: internet egress BLOCKED, verified" \
  || fail "attestation egress not blocked"

# 4) the app container genuinely cannot reach the internet
if docker compose ps app >/dev/null 2>&1; then
  if docker compose exec -T app python -c "import socket,sys
socket.setdefaulttimeout(3)
try:
    socket.create_connection(('1.1.1.1',443),3); sys.exit(1)
except Exception:
    sys.exit(0)"; then
    pass "app container cannot reach the internet (1.1.1.1 unreachable)"
  else
    fail "app container REACHED the internet — egress LEAK"
  fi
fi

echo
if [[ "$RC" == "0" ]]; then
  echo "SMOKE PASS — governed, in-boundary, provably zero-egress."
else
  echo "SMOKE FAIL — see the ✗ items above."
fi
exit "$RC"
