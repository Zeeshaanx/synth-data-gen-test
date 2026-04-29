#!/bin/bash
# =============================================================================
# setup.sh — NeMo Data Designer: One-shot setup script
# Run this ONCE on a fresh Ubuntu 22.04 EC2 instance (r5.large or bigger).
# Everything installs, configures, and starts automatically.
# When done, create an AMI from this instance for distribution.
#
# Usage:
#   git clone https://github.com/YOUR_ORG/synth-data-gen.git
#   cd synth-data-gen
#   chmod +x setup.sh
#   ./setup.sh
# =============================================================================

set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[$(date '+%H:%M:%S')]${RESET} $1"; }
ok()   { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✅ $1${RESET}"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠️  $1${RESET}"; }
die()  { echo -e "${RED}[$(date '+%H:%M:%S')] ❌ $1${RESET}"; exit 1; }

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$REPO_DIR/src/NemoDataDesignerAPI"
VENV_DIR="$REPO_DIR/src/venv"
SECRETS_DIR="/etc/synth-secrets"
SYSTEMD_DIR="/etc/systemd/system"

echo ""
echo -e "${BOLD}================================================${RESET}"
echo -e "${BOLD}   NeMo Data Designer — Setup Script${RESET}"
echo -e "${BOLD}================================================${RESET}"
echo ""

# ── Must run as ubuntu user (not root) ───────────────────────────────────────
if [ "$EUID" -eq 0 ]; then
    die "Do not run as root. Run as ubuntu: ./setup.sh"
fi

# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — PostgreSQL password
# ═════════════════════════════════════════════════════════════════════════════
echo ""
log "STEP 1/8 — PostgreSQL credentials"

if [ -f "$SECRETS_DIR/postgres.env" ]; then
    warn "Secrets file already exists at $SECRETS_DIR/postgres.env — skipping password prompt"
    source "$SECRETS_DIR/postgres.env"
else
    # Auto-generate a strong random password — no user input needed
    PG_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    log "Generated PostgreSQL password automatically (stored securely, never printed)"

    sudo mkdir -p "$SECRETS_DIR"
    sudo chmod 700 "$SECRETS_DIR"
    sudo bash -c "cat > $SECRETS_DIR/postgres.env" << ENVEOF
PG_PASSWORD=${PG_PASSWORD}
PG_USER=synthuser
PG_DB=synthdb
PG_PORT=5432
DATABASE_URL=postgresql://synthuser:${PG_PASSWORD}@127.0.0.1:5432/synthdb
ENVEOF
    sudo chmod 600 "$SECRETS_DIR/postgres.env"
    sudo chown root:root "$SECRETS_DIR/postgres.env"
fi

# Load vars for use in this script
source "$SECRETS_DIR/postgres.env"
ok "Credentials secured at $SECRETS_DIR/postgres.env (root-only, mode 600)"

# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — System packages
# ═════════════════════════════════════════════════════════════════════════════
echo ""
log "STEP 2/8 — Installing system packages"

sudo apt-get update -qq
sudo apt-get install -y \
    python3.11 python3.11-venv python3.11-dev \
    build-essential nginx git curl wget unzip \
    ca-certificates gnupg openssl python3-yaml \
    2>&1 | grep -E "(Unpacking|Setting up|already)" || true

ok "System packages installed"

# ── Docker (official repo, not snap) ─────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    log "Installing Docker..."
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y \
        docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
else
    warn "Docker already installed — skipping"
fi

sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu
sudo chmod 666 /var/run/docker.sock
ok "Docker ready"

# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — PostgreSQL (Docker, own systemd unit)
# ═════════════════════════════════════════════════════════════════════════════
echo ""
log "STEP 3/8 — Setting up PostgreSQL 16 (Docker)"

sudo mkdir -p /opt/synth-postgres/data
sudo chown ubuntu:ubuntu /opt/synth-postgres/data

docker pull postgres:16-alpine 2>&1 | tail -1

sudo bash -c "cat > $SYSTEMD_DIR/synth_postgres.service" << SVCEOF
[Unit]
Description=Synth Data Gen — PostgreSQL 16
After=docker.service
Requires=docker.service

[Service]
Restart=always
RestartSec=10
TimeoutStartSec=120
EnvironmentFile=$SECRETS_DIR/postgres.env
ExecStartPre=-/usr/bin/docker rm -f synth_postgres
ExecStart=/usr/bin/docker run --rm \\
  --name synth_postgres \\
  -e POSTGRES_USER=\${PG_USER} \\
  -e POSTGRES_PASSWORD=\${PG_PASSWORD} \\
  -e POSTGRES_DB=\${PG_DB} \\
  -e PGDATA=/var/lib/postgresql/data/pgdata \\
  -v /opt/synth-postgres/data:/var/lib/postgresql/data \\
  -p 127.0.0.1:\${PG_PORT}:5432 \\
  postgres:16-alpine
ExecStop=/usr/bin/docker stop synth_postgres

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable synth_postgres
sudo systemctl restart synth_postgres

# Wait for postgres to be ready
log "Waiting for PostgreSQL to accept connections..."
for i in $(seq 1 24); do
    if docker exec synth_postgres pg_isready -U "$PG_USER" -d "$PG_DB" &>/dev/null; then
        ok "PostgreSQL is ready"
        break
    fi
    [ $i -eq 24 ] && die "PostgreSQL did not become ready after 2 minutes"
    sleep 5
done

# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — Python virtual environment + dependencies
# ═════════════════════════════════════════════════════════════════════════════
echo ""
log "STEP 4/8 — Python environment"

python3.11 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet

log "Installing Python requirements (this takes a few minutes)..."
"$VENV_DIR/bin/pip" install \
    --prefer-binary \
    --timeout 600 \
    -r "$REPO_DIR/requirements.txt" \
    --quiet

ok "Python environment ready"

# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 — NeMo Microservices setup
# ═════════════════════════════════════════════════════════════════════════════
echo ""
log "STEP 5/8 — NeMo Microservices setup (20-40 min — Docker images are large)"

chmod +x "$REPO_DIR/src/nemo_setup.sh"
cd "$REPO_DIR/src"
bash nemo_setup.sh
cd "$REPO_DIR"

ok "NeMo setup complete"

# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 — FastAPI systemd service
# ═════════════════════════════════════════════════════════════════════════════
echo ""
log "STEP 6/8 — FastAPI service"

# Generate proxy secret key
PROXY_SECRET_KEY=$(openssl rand -base64 32)
# Append to secrets file (root-only)
sudo bash -c "echo 'PROXY_SECRET_KEY=${PROXY_SECRET_KEY}' >> $SECRETS_DIR/postgres.env"

sudo bash -c "cat > $SYSTEMD_DIR/nemo_data_designer.service" << SVCEOF
[Unit]
Description=NeMo Data Designer — FastAPI Gateway
After=network.target synth_postgres.service nemo-data-designer.service
Wants=synth_postgres.service

[Service]
User=ubuntu
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=$SECRETS_DIR/postgres.env

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable nemo_data_designer
sudo systemctl restart nemo_data_designer

# Wait for FastAPI to be up
log "Waiting for FastAPI to respond..."
for i in $(seq 1 24); do
    if curl -sf http://127.0.0.1:8000/ok &>/dev/null; then
        ok "FastAPI is up"
        break
    fi
    [ $i -eq 24 ] && die "FastAPI did not start. Check: sudo journalctl -u nemo_data_designer -n 50"
    sleep 5
done

# ═════════════════════════════════════════════════════════════════════════════
# STEP 7 — Nginx reverse proxy
# ═════════════════════════════════════════════════════════════════════════════
echo ""
log "STEP 7/8 — Nginx"

sudo bash -c "cat > /etc/nginx/sites-available/nemo_proxy" << 'NGINXEOF'
server {
    listen 80 default_server;

    # Health check
    location /health {
        return 200 'ok';
        add_header Content-Type text/plain;
    }

    # Main app — strip /synth-data-gen prefix, proxy to FastAPI
    location /synth-data-gen/ {
        add_header Access-Control-Allow-Origin  "*" always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Authorization, Content-Type" always;

        if ($request_method = OPTIONS) { return 204; }

        proxy_pass         http://127.0.0.1:8000/;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600;

        # Seed CSV uploads can be large
        client_max_body_size 100M;
    }

    # Redirect root to home UI
    location = / {
        return 302 /synth-data-gen/data_generation/v1/home;
    }
}
NGINXEOF

sudo ln -sf /etc/nginx/sites-available/nemo_proxy /etc/nginx/sites-enabled/nemo_proxy
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

ok "Nginx configured"

# ═════════════════════════════════════════════════════════════════════════════
# STEP 8 — Final health checks
# ═════════════════════════════════════════════════════════════════════════════
echo ""
log "STEP 8/8 — Final health checks"

ALL_OK=true

check() {
    local label="$1"; local cmd="$2"
    if eval "$cmd" &>/dev/null; then
        ok "$label"
    else
        warn "$label — NOT READY (check logs below)"
        ALL_OK=false
    fi
}

check "PostgreSQL"  "docker exec synth_postgres pg_isready -U $PG_USER -d $PG_DB"
check "NeMo API"    "curl -sf http://127.0.0.1:8080/v1/data-designer/jobs"
check "FastAPI"     "curl -sf http://127.0.0.1:8000/ok"
check "Nginx"       "curl -sf http://127.0.0.1/synth-data-gen/ok"

# Get public IP for output
PUBLIC_IP=$(curl -sf --max-time 3 \
    -H "X-aws-ec2-metadata-token: $(curl -sf -X PUT \
        'http://169.254.169.254/latest/api/token' \
        -H 'X-aws-ec2-metadata-token-ttl-seconds: 10' 2>/dev/null)" \
    http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null \
    || hostname -I | awk '{print $1}')

echo ""
echo -e "${BOLD}================================================${RESET}"
if [ "$ALL_OK" = true ]; then
    echo -e "${GREEN}${BOLD}   ✅ SETUP COMPLETE${RESET}"
    echo -e "${BOLD}================================================${RESET}"
    echo ""
    echo -e "  ${BOLD}Frontend:${RESET}  http://${PUBLIC_IP}/synth-data-gen/data_generation/v1/home"
    echo -e "  ${BOLD}Jobs UI:${RESET}   http://${PUBLIC_IP}/synth-data-gen/data_generation/v1/jobs/ui"
    echo -e "  ${BOLD}API:${RESET}       http://${PUBLIC_IP}/synth-data-gen/data_generation/v1/create"
    echo -e "  ${BOLD}Health:${RESET}    http://${PUBLIC_IP}/synth-data-gen/ok"
    echo ""
    echo -e "${CYAN}  Ready to bake into an AMI.${RESET}"
else
    echo -e "${YELLOW}${BOLD}   ⚠️  SETUP DONE WITH WARNINGS${RESET}"
    echo -e "${BOLD}================================================${RESET}"
    echo ""
    echo "  Some services aren't ready yet. Check logs:"
    echo "    sudo journalctl -u nemo_data_designer -n 50 --no-pager"
    echo "    sudo journalctl -u synth_postgres -n 30 --no-pager"
    echo "    sudo journalctl -u nemo-data-designer -n 50 --no-pager"
fi
echo -e "${BOLD}================================================${RESET}"
echo ""
