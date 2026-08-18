# Deploy Precepta on AWS (EC2)

The right way to host Precepta: a **VM you control** with a **persistent disk** —
which is exactly the sovereign, self-hosted model. This runs the **full stack**
(bundled models + zero-egress + the Console), and sessions/keys/audit **persist**,
so Google login sticks (unlike Vercel/serverless).

> Use **EC2** (a virtual machine). Do **not** use Lambda / App Runner —
> serverless has a read-only, ephemeral disk and hits the same wall as Vercel.

---

## 0. Before you start
- An AWS account, and the domain **console.preceptaai.com** under your control.
- Your Google OAuth **Web** client (Google Cloud → Credentials).
- ~15 minutes.

## 1. Launch the EC2 instance
AWS Console → **EC2 → Launch instance**:
- **Name:** `precepta`
- **AMI:** Ubuntu Server 24.04 LTS (x86_64)
- **Instance type:** `t3.large` (2 vCPU / 8 GB — comfortable for the bundled
  `llama3.2:3b`). `t3.medium` (4 GB) works for a lighter demo.
- **Key pair:** create one and download the `.pem` (for SSH).
- **Network / Security group:** allow inbound
  - **SSH (22)** from *My IP*
  - **HTTP (80)** from Anywhere
  - **HTTPS (443)** from Anywhere
- **Storage:** 30 GB gp3 (room for models + DB).
- **Advanced details → User data:** paste the contents of
  [`deploy/ec2-user-data.sh`](ec2-user-data.sh) (installs Docker + clones the repo
  automatically). *Optional but recommended.*
- **Launch.**

Then give it a fixed address: **EC2 → Elastic IPs → Allocate → Associate** to this
instance. Note the IP (e.g. `13.51.xx.xx`).

## 2. Point the domain at it
At your DNS provider (Route 53 or your registrar), create an **A record**:
`console.preceptaai.com → <Elastic IP>`. **Remove the domain from the old Vercel
project first** so it stops answering.

## 3. Google OAuth (so sign-in works)
In your Google OAuth client, add **Authorized redirect URI**:
`https://console.preceptaai.com/auth/sso/callback`
(If the client is in *Testing* mode, add your email under *Test users*.)

## 4. Connect + configure
```bash
chmod 400 precepta-key.pem
ssh -i precepta-key.pem ubuntu@<Elastic IP>

# (if you did NOT use the user-data script, install Docker + git and
#  `git clone https://github.com/LiminaLabsAI/precepta.git /opt/precepta` first)

cd /opt/precepta
cp deploy/.env.example deploy/.env
nano deploy/.env
```
Set at least:
```bash
ORG_NAME="Precepta"
ADMIN_EMAIL="123.sarang@gmail.com"
PRECEPTA_PLATFORM_OWNERS="123.sarang@gmail.com"
PUBLIC_DOMAIN="console.preceptaai.com"
# Google sign-in (leave unset to use local-admin login only):
OIDC_ISSUER="https://accounts.google.com"
OIDC_CLIENT_ID="492495778264-...apps.googleusercontent.com"
OIDC_CLIENT_SECRET="<your secret>"
PRECEPTA_ADMIN_EMAILS="123.sarang@gmail.com"
# leave OIDC_REDIRECT unset — it auto-derives to your domain's callback
```

## 5. Start it (persistent + auto-HTTPS + Google-reachable)
```bash
PUBLIC_DOMAIN=console.preceptaai.com docker compose \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.egress.yml \
  -f deploy/docker-compose.public.yml up -d --build
```
- `docker-compose.public.yml` → Caddy serves `console.preceptaai.com` on 80/443
  and gets a **real TLS cert automatically** (needs DNS + ports open first).
- `docker-compose.egress.yml` → lets the app reach Google for the OIDC token
  exchange (Google hosts auto-approve; disclosed in the attestation).
- First run pulls the models (a few minutes).

## 6. Verify
```bash
curl -s https://console.preceptaai.com/auth/sso/status   # -> "configured": true
docker compose ps                                        # all services up
```
Open **https://console.preceptaai.com** → **Sign in with Google** → you land on
the console and **stay** logged in (the session is saved on the instance's disk).

## Operate
- Logs: `docker compose logs -f app`
- Update: `git pull && PUBLIC_DOMAIN=console.preceptaai.com docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.egress.yml -f deploy/docker-compose.public.yml up -d --build`
- Data lives in the `precepta_data` Docker volume (survives restarts/updates).
  Back it up with a snapshot of the EBS volume.

## Cost (rough)
`t3.large` ≈ $60/mo on-demand (cheaper with a Savings Plan / reserved), plus the
EBS volume (~$3/mo for 30 GB) and Elastic IP (free while attached). `t3.medium`
≈ $30/mo for a lighter box.
