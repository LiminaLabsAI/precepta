#!/usr/bin/env bash
# Append an event line to today's ecosystem session log.
#
# Sourced by core/scripts/check-history-reminder.sh (via the existing
# PostToolUse hook installed by `momentum init`). Safe to invoke
# anywhere — no-ops silently when the current directory is not inside
# a registered ecosystem member.
#
# Inputs (positional):
#   $1 — event kind  (commit | pr | deploy | log)
#   $2 — event summary (one line, no embedded newlines)
#   $3 — optional context (sha, PR number, deploy tag, …)
#
# Resolves the ecosystem root by walking up from $PWD looking for a
# sibling directory containing ecosystem.json (bounded to 5 parents by
# default; override via MOMENTUM_MAX_PARENT_WALK env var — see
# core/ecosystem/lib/state.js for the JS counterpart).
# Resolves the member id by matching $PWD against the manifest's
# members[].path entries.
#
# Writes one line to <ecosystem-root>/sessions/$(date -u +%F).md:
#   HH:MMZ [<member-id>] <kind> <summary> (<context>)
#
# If this is the first append today, prepends a header line naming the
# active initiative (if any).

set -eu

EVENT_KIND="${1:-}"
EVENT_SUMMARY="${2:-}"
EVENT_CONTEXT="${3:-}"

if [ -z "$EVENT_KIND" ] || [ -z "$EVENT_SUMMARY" ]; then
  exit 0
fi

# ── Resolve ecosystem root (bounded walk-up, looking for siblings) ──────────
# The ecosystem is a SIBLING of member repos. From a member repo we walk
# up one level and look at each sibling for ecosystem.json.

find_ecosystem_root() {
  local start="$PWD"
  local current="$start"
  local depth=0
  local max_depth="${MOMENTUM_MAX_PARENT_WALK:-5}"
  # Guard against non-numeric / negative env value.
  case "$max_depth" in
    ''|*[!0-9]*) max_depth=5 ;;
  esac
  while [ $depth -le $max_depth ]; do
    # Same-directory check (caller might already be in ecosystem root)
    if [ -f "$current/ecosystem.json" ]; then
      echo "$current"
      return 0
    fi
    # Sibling check
    local parent
    parent=$(dirname "$current")
    if [ "$parent" = "$current" ]; then return 1; fi
    for sibling in "$parent"/*; do
      if [ -d "$sibling" ] && [ -f "$sibling/ecosystem.json" ]; then
        echo "$sibling"
        return 0
      fi
    done
    current="$parent"
    depth=$((depth + 1))
  done
  return 1
}

ROOT=$(find_ecosystem_root 2>/dev/null) || exit 0
[ -z "$ROOT" ] && exit 0
[ -f "$ROOT/ecosystem.json" ] || exit 0

# ── Resolve member id by matching $PWD against manifest.members[].path ─────

resolve_member_id() {
  python3 - "$ROOT" "$PWD" <<'PY' 2>/dev/null || echo ""
import sys, json, os
root, pwd = sys.argv[1], os.path.realpath(sys.argv[2])
try:
    with open(os.path.join(root, "ecosystem.json")) as f:
        m = json.load(f)
except Exception:
    sys.exit(0)
for member in m.get("members", []):
    abs_path = os.path.realpath(os.path.join(root, member.get("path", "")))
    # Match pwd that is == abs_path or any descendant
    try:
        rel = os.path.relpath(pwd, abs_path)
    except ValueError:
        continue
    if rel == "." or (not rel.startswith("..") and not os.path.isabs(rel)):
        print(member.get("id", ""))
        sys.exit(0)
PY
}

MEMBER_ID=$(resolve_member_id)
[ -z "$MEMBER_ID" ] && exit 0

# ── Write the line ─────────────────────────────────────────────────────────

SESSION_DIR="$ROOT/sessions"
mkdir -p "$SESSION_DIR"
TODAY=$(date -u +%F)
SESSION_FILE="$SESSION_DIR/$TODAY.md"
HHMM=$(date -u +%H:%M)

# ── BUG-004 fix: serialize concurrent writers via mkdir lock ────────────────
# `mkdir` is atomic on POSIX filesystems and portable across macOS/Linux
# without depending on flock (which is not present by default on macOS).
# The lock covers the "check + header-write + append" sequence so two
# concurrent commits in different member repos can't both write the
# header or interleave their data lines.
LOCK_DIR="$SESSION_FILE.lock"
acquire_session_lock() {
  local tries=100  # ~5s total at 50ms each
  while [ $tries -gt 0 ]; do
    if mkdir "$LOCK_DIR" 2>/dev/null; then
      return 0
    fi
    sleep 0.05
    tries=$((tries - 1))
  done
  return 1
}
release_session_lock() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap release_session_lock EXIT INT TERM

# If we cannot acquire the lock within the budget, drop the event silently
# rather than corrupt the file. Session events are advisory; momentum's
# correctness does not depend on every one landing.
if ! acquire_session_lock; then
  exit 0
fi

# First write of the day → write header (and active initiative banner).
if [ ! -f "$SESSION_FILE" ]; then
  {
    echo "# Session $TODAY"
    if [ -f "$ROOT/.state/active-initiative" ]; then
      ACTIVE=$(tr -d '[:space:]' < "$ROOT/.state/active-initiative")
      if [ -n "$ACTIVE" ]; then
        echo "Active initiative: $ACTIVE"
      fi
    fi
    echo ""
  } > "$SESSION_FILE"
fi

# Build the line; quote context only if present.
if [ -n "$EVENT_CONTEXT" ]; then
  echo "${HHMM}Z [$MEMBER_ID] ${EVENT_KIND}: ${EVENT_SUMMARY} (${EVENT_CONTEXT})" >> "$SESSION_FILE"
else
  echo "${HHMM}Z [$MEMBER_ID] ${EVENT_KIND}: ${EVENT_SUMMARY}" >> "$SESSION_FILE"
fi

# Cache last session date for cheap subsequent reads.
mkdir -p "$ROOT/.state"
echo "$TODAY" > "$ROOT/.state/last-session"

# Lock is released by the EXIT trap.
exit 0
