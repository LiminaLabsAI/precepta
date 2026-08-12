# Run Precepta inside your network

A single-node, **egress-locked** deployment: the control plane and the AI models
run on your machine, the app has **no route to the internet**, and you get a
signed **zero-egress attestation** to prove it. Great for a pilot or evaluation.

> **You need:** a Linux or macOS machine with **Docker** installed and ~16 GB RAM.
> That's it. (A GPU is optional — see *Models* below.)

---

## 5 steps (~10 minutes)

### 1. Get the files
```bash
git clone https://github.com/LiminaLabsAI/precepta.git && cd precepta
```

### 2. Check your machine is ready
```bash
./deploy/doctor.sh
```
You'll see a checklist (`✓ Docker · ✓ port 8000 free · ✓ .env`). Each `✗` tells
you exactly how to fix it.

### 3. Set your details
```bash
cp deploy/.env.example deploy/.env
```
Open `deploy/.env` and fill in the top three lines (each is explained in place):
`ORG_NAME`, `ADMIN_EMAIL`, `PRECEPTA_PLATFORM_OWNERS`. Leave the rest — they're
already the sovereign, in-boundary defaults.

### 4. Start it
```bash
./deploy/up.sh
```
This builds the app, pulls the AI models **onto your machine** (one time, a few
minutes), and starts everything **locked off from the internet**. When it's ready
you'll see the Console URL.

### 5. Open it and prove it
Go to **http://127.0.0.1:8000/console**, sign in with your `ADMIN_EMAIL`, and open
**Deployment** in the left menu. You'll see live status and can **generate the
attestation** — it reports `egress: blocked, verified`, the signed proof nothing
left your network.

**Next:** add your own model endpoints under **Inference plane** and you're live.

---

## How the sovereignty works (plain words)
- The **app** (which sees your prompts) runs on a Docker network with **no way to
  reach the internet** — proven by an outbound probe recorded in the attestation.
- The **router's own model** and the **embeddings** run on a bundled, in-boundary
  **Ollama** — so classifying/routing a request never sends the prompt out.
- A small **front-door proxy** is the only inbound path (so you can open the
  Console) — it never carries your data outward.

## Models
- Defaults are small and CPU-friendly (`llama3.2:3b`, `nomic-embed-text`) so it
  runs anywhere. Change `ROUTER_MODEL` / `EMBED_MODEL` in `.env` for larger ones.
- **GPU:** uncomment the `deploy` block under the `ollama` service in
  `docker-compose.yml` to pass an NVIDIA GPU through.

## Everyday commands
```bash
docker compose -f deploy/docker-compose.yml logs -f app   # follow logs
docker compose -f deploy/docker-compose.yml ps            # what's running
docker compose -f deploy/docker-compose.yml down          # stop (data + models persist)
./deploy/up.sh                                            # start again
```

## Troubleshooting
| Symptom | Fix |
|---|---|
| `doctor.sh` says Docker not running | Start Docker Desktop / the engine, re-run. |
| Port 8000 already in use | Stop the other process, or change the app port in `docker-compose.yml`. |
| First request is slow (~30–80s) | The model is loading into memory on the first call; later calls are fast. |
| Model pull fails | The pull needs internet on first run; for a fully offline site, pre-bake the `ollama_data` volume. |
| Console blank | The stack isn't up — run `./deploy/up.sh`, then reload. |

## Restricted egress (opt-in) — using a cloud endpoint

By default the app has **no path to the internet** (the `internal` network), so a
cloud inference endpoint (Hugging Face, Neysa, …) will show as **Unreachable** —
that is the sealed guarantee working, not a bug.

If you *want* to route to a specific cloud endpoint, do **two** things:

1. **Approve its host** in the Console: **Settings → Egress → Approve** (e.g.
   `huggingface.co`). Owner-only and audited; the attestation posture changes
   from `sealed` to `restricted` and lists exactly which hosts are approved.
2. **Turn on the egress broker** — start with restricted egress enabled:

   ```bash
   RESTRICTED_EGRESS=1 ./deploy/up.sh
   ```

How it stays sovereign: the **app never gets a direct internet route** — it stays
on the `internal` network, so the attestation's egress probe *still* proves it
cannot reach the internet on its own. Its outbound HTTPS is sent through a small
**egress broker** (`app/sovereign/broker.py`) that runs between the internal and
egress networks and opens a tunnel **only** to the hosts you approved (read live
from the allowlist — approving/revoking takes effect immediately). Unapproved
hosts — and any direct connection attempt — are refused. So the guarantee shifts
honestly from *"nothing can leave"* to *"the app has no direct egress; it can
reach only the named hosts you approved, through an audited broker."*

> **The strongest posture is the default** (no `RESTRICTED_EGRESS`, no approved
> hosts, no broker). Only opt in if a pilot genuinely needs a cloud model.

## What this pilot deploy is **not** (yet)
High-availability / multi-node, Kubernetes/Helm, Postgres, a secrets vault,
offline (air-gapped) install media, and directory user-sync are **deferred** to
the production package. This is the smallest complete thing that is truly
sovereign and installable.
