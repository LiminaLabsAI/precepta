# `licensing/` — Precepta vendor licensing service

**This is the vendor's control server, NOT the sovereign self-host image.** It
holds the private signing key and the admin surface — keep it off customer
machines. See [`docs/licensing.md`](../docs/licensing.md) for the model.

## Run (local)

```bash
pip install -r licensing/requirements.txt
LICENSE_DB=licensing/data/licensing.db \
GOOGLE_CLIENT_ID=<your-web-oauth-client-id> \
LICENSE_ADMIN_TOKEN=<a-strong-token> \
uvicorn licensing.service:app --port 8099
```

- Onboarding site: `http://127.0.0.1:8099/`
- Admin dashboard: `http://127.0.0.1:8099/admin` (enter the admin token)

## Config (env)

| Var | Purpose | Default |
|---|---|---|
| `LICENSE_SIGNING_KEY` | base64url raw Ed25519 **private** key (signs licenses) | dev key (⚠️ set in prod) |
| `LICENSE_PUBLIC_KEY` | matching public key (the app embeds this in Phase 17) | dev key |
| `GOOGLE_CLIENT_ID` | Web OAuth client id (verify sign-ins; shown to the site) | — |
| `LICENSE_ADMIN_TOKEN` | bearer token for `/admin*` | `dev-admin` (⚠️ set in prod) |
| `LICENSE_DB` | SQLite path | `licensing/data/licensing.db` |
| `PRECEPTA_REPO_URL` | clone URL shown in the install steps | LiminaLabsAI/precepta |

Generate a production keypair:

```bash
python -c "from licensing import core; a,b=core.generate_keypair(); print('LICENSE_SIGNING_KEY='+a); print('LICENSE_PUBLIC_KEY='+b)"
```

## Deploy

Needs an **always-on host with a writable disk** for the SQLite DB (a small VM,
Render/Railway with a volume, Fly, etc.) — **not** a static/serverless host.
Serve it at your onboarding domain (e.g. `console.preceptaai.com`), set
`GOOGLE_CLIENT_ID` and add that origin as an **Authorized JavaScript origin** in
your Google OAuth client. Set `LICENSE_SIGNING_KEY` + `LICENSE_ADMIN_TOKEN` as
secrets.

## Endpoints

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/` | public | onboarding site |
| GET | `/onboard/config` | public | the (public) Google client id for GIS |
| POST | `/onboard` | public | verify Google token → record login → issue trial key + steps |
| POST | `/license/heartbeat` | installs | metadata-only install check-in (Phase 17 client) → returns plan/state |
| GET | `/admin`, `/admin/{logins,licenses,installs}` | admin | visibility |
| POST | `/admin/licenses/{id}/plan` · `/revoke` | admin | change plan (re-issues a key) / revoke |

## Phase 17 hook

The self-host app will call `POST {PRECEPTA_LICENSE_URL}/license/heartbeat`
(default `PRECEPTA_LICENSE_URL=https://console.preceptaai.com`), auto-approve that
host in its egress allowlist, and disclose it in the attestation.
