#!/usr/bin/env bash
# EC2 user-data (cloud-init) — one-time OS prep for Precepta on Ubuntu 22.04/24.04.
#
# Paste this into "Advanced details → User data" when launching the instance. It
# installs Docker + the compose plugin and clones the repo to /opt/precepta. It
# does NOT start the app (that needs your secrets in deploy/.env) — after boot,
# SSH in and follow deploy/aws-ec2.md (fill .env, run the compose up).
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y ca-certificates curl git

# Docker (official repo)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker ubuntu || true

# App code
git clone https://github.com/LiminaLabsAI/precepta.git /opt/precepta || true
chown -R ubuntu:ubuntu /opt/precepta
cat > /opt/precepta/FIRST_BOOT_README.txt <<'EOF'
Precepta is cloned here. To start it:
  cd /opt/precepta
  cp deploy/.env.example deploy/.env   # then edit: ORG_NAME, ADMIN_EMAIL,
                                       # PRECEPTA_PLATFORM_OWNERS, OIDC_* (Google)
  PUBLIC_DOMAIN=console.preceptaai.com docker compose \
    -f deploy/docker-compose.yml \
    -f deploy/docker-compose.egress.yml \
    -f deploy/docker-compose.public.yml up -d --build
See deploy/aws-ec2.md for the full runbook.
EOF
