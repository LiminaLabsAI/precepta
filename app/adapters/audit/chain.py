"""Tamper-evident audit chain (DESIGN.md §4, §6).

SHA-256 hash chain over `tamper_evident_audit_log`. Each event hashes its fields
plus the previous event's hash; genesis = 64 zeros. Chain order = insertion
order (rowid), so verification is independent of wall-clock collisions.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid

from ...db import get_conn

GENESIS = "0" * 64
_FIELDS = ("event_id", "timestamp", "event_type", "actor", "resource",
           "action", "outcome", "metadata", "previous_hash")


def _hash(row: dict) -> str:
    payload = "|".join(str(row[f]) for f in _FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_rows(rows: list[dict]) -> bool:
    """Pure verifier: walk rows in order, checking linkage + recomputed hash."""
    prev = GENESIS
    for r in rows:
        if r["previous_hash"] != prev:
            return False
        if _hash(r) != r["event_hash"]:
            return False
        prev = r["event_hash"]
    return True


class AuditChain:
    def append(self, event_type: str, actor: str, resource: str, action: str,
               outcome: str, metadata: dict) -> str:
        eid = uuid.uuid4().hex
        ts = time.time_ns()
        meta = json.dumps(metadata, sort_keys=True)
        with get_conn() as conn:
            last = conn.execute(
                "SELECT event_hash FROM tamper_evident_audit_log ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            prev = last["event_hash"] if last else GENESIS
            row = {"event_id": eid, "timestamp": ts, "event_type": event_type,
                   "actor": actor, "resource": resource, "action": action,
                   "outcome": outcome, "metadata": meta, "previous_hash": prev}
            row["event_hash"] = _hash(row)
            conn.execute(
                "INSERT INTO tamper_evident_audit_log (event_id,timestamp,event_type,"
                "actor,resource,action,outcome,metadata,previous_hash,event_hash) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                tuple(row[f] for f in _FIELDS) + (row["event_hash"],),
            )
        return eid

    def verify(self) -> bool:
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM tamper_evident_audit_log ORDER BY rowid ASC").fetchall()]
        return verify_rows(rows)

    def count(self) -> int:
        with get_conn() as conn:
            return int(conn.execute(
                "SELECT COUNT(*) c FROM tamper_evident_audit_log").fetchone()["c"])

    def recent(self, limit: int = 25) -> list[dict]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tamper_evident_audit_log ORDER BY rowid DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    def export(self) -> dict:
        """Full chain export (WORM-ready) — rows + head + verification."""
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM tamper_evident_audit_log ORDER BY rowid ASC").fetchall()]
        return {"genesis": GENESIS, "events": len(rows),
                "verified": verify_rows(rows), "head": self.head_hash(), "chain": rows}

    def head_hash(self) -> str:
        with get_conn() as conn:
            last = conn.execute(
                "SELECT event_hash FROM tamper_evident_audit_log ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        return last["event_hash"] if last else GENESIS


_chain = AuditChain()


def get_chain() -> AuditChain:
    return _chain
