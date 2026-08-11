"""Demo seed — realistic sample policies + API keys for a live demonstration.

Idempotent: it skips anything already present (by name), so it's safe to run
repeatedly. It writes real rows through the same stores the Console uses, so the
seeded data shows up exactly like hand-created data — and is governed for real.

Run it inside a running deployment:
    ./deploy/seed-demo.sh
    # or, directly:
    docker compose -f deploy/docker-compose.yml exec app python -m app.demo_seed
"""
from __future__ import annotations


# ── sample policies (only the fields Precepta actually enforces) ────────────
# Each: (name, description, action_type, effect, conditions)
_POLICIES = [
    ("Block foreign LLM providers",
     "Sovereignty: never let a request reach a public US LLM API — keep inference in-boundary.",
     "chat.completion", "block",
     {"url_blocklist": ["openai.com", "anthropic.com", "googleapis.com", "azure.com"]}),
    ("Rate limit — 120 requests/hour per app",
     "Abuse control: cap how fast any single app can call the gateway.",
     "chat.completion", "block",
     {"max_calls_per_hour": 120}),
    ("Flag requests with no data-classification tag",
     "Governance: warn (don't block) when a request doesn't declare its data sensitivity.",
     "chat.completion", "warn",
     {"require_data_tag": True}),
    ("Scan model output for PII",
     "Privacy: redact emails, phone and card numbers from answers before they leave.",
     "chat.completion", "warn",
     {"pii_filter_output": True}),
]

# ── sample keys (budgets live on the KEY — cost + tokens) ───────────────────
# Each: name, role, team, expires_in_days, cost_daily, cost_monthly,
#       token_daily, token_monthly
_KEYS = [
    ("mobile-app",       "user",    "product",  90,   5.0, 100.0,        0,          0),
    ("analytics-batch",  "user",    "data",     90,   0.0,  50.0,        0,  2_000_000),
    ("partner-readonly", "auditor", "partners", 30,   0.0,   0.0,        0,          0),
    ("internal-dev",     "admin",   "platform", None, 0.0,   0.0,        0,          0),
]


def seed_policies() -> list[str]:
    from .governance import policy as P
    existing = {p.get("name") for p in P.list_all()}
    created = []
    for name, desc, action, effect, cond in _POLICIES:
        if name in existing:
            continue
        P.create_policy(name, desc, action, effect, cond, {})
        created.append(name)
    return created


def seed_keys() -> list[dict]:
    from .adapters.identity.keys import list_keys, issue_key
    existing = {k.get("name") for k in list_keys()}
    created = []
    for name, role, team, exp, cd, cm, td, tm in _KEYS:
        if name in existing:
            continue
        _id, token = issue_key(name, role=role, team=team, expires_in_days=exp,
                               cost_cap_daily=cd, cost_cap_monthly=cm,
                               token_cap_daily=td, token_cap_monthly=tm)
        created.append({"name": name, "token": token})   # token shown once, at creation
    return created


def seed() -> dict:
    return {"policies_created": seed_policies(), "keys_created": seed_keys()}


if __name__ == "__main__":
    r = seed()
    pols = r["policies_created"]
    keys = r["keys_created"]
    print("Seeded demo data:")
    print("  policies:", ", ".join(pols) if pols else "(all already present)")
    if keys:
        print("  keys (token shown once — copy now if you need it):")
        for k in keys:
            print(f"    - {k['name']}: {k['token']}")
    else:
        print("  keys:     (all already present)")
    print("\nOpen the Console → Policies and Keys & budgets to see them.")
