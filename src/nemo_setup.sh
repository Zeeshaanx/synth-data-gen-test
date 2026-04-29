#!/bin/bash
set -e

# --- CONFIGURATION ---
API_KEY="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"
ORG_ID="0892923046583261"
NEMO_TAG="25.12"
USER_HOME="/home/ubuntu"
INSTALL_DIR="${USER_HOME}/nemo-microservices-quickstart_v${NEMO_TAG}"

echo ">>> 🚀 Starting Production Setup for NeMo Data Designer..."

# --- 1. SYSTEM PREP: SWAP MEMORY ---
if [ ! -f /swapfile ]; then
    echo ">>> 🧠 Creating 8GB Swap file..."
    sudo fallocate -l 8G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
else
    echo ">>> ✅ Swap file already exists."
fi

# --- 2. INSTALL DOCKER ---
echo ">>> 🐳 Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y ca-certificates curl gnupg unzip
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
    echo "Docker is already installed."
fi

sudo groupadd -f docker
sudo usermod -aG docker $USER
sudo chmod 666 /var/run/docker.sock

# --- 3. INSTALL NVIDIA NGC CLI ---
echo ">>> ⬇️ Installing NGC CLI..."
export NGC_CLI_API_KEY="$API_KEY"
export NGC_CLI_ORG="$ORG_ID"
export NGC_CLI_FORMAT_TYPE="json"

mkdir -p ${USER_HOME}/ngc-cli
cd ${USER_HOME}/ngc-cli
if [ ! -f ngccli_linux.zip ]; then
    wget --quiet --content-disposition https://api.ngc.nvidia.com/v2/resources/nvidia/ngc-apps/ngc_cli/versions/4.12.0/files/ngccli_linux.zip -O ngccli_linux.zip
    unzip -qo ngccli_linux.zip
    chmod u+x ngc-cli/ngc
fi
export PATH="$PATH:${USER_HOME}/ngc-cli/ngc-cli"

# --- 4. DOWNLOAD NEMO ARTIFACTS ---
echo ">>> 🔑 Logging into NVIDIA Registry..."
echo "$API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin

echo ">>> 📦 Downloading/Verifying NeMo Quickstart ($NEMO_TAG)..."
cd ${USER_HOME}
if [ ! -d "$INSTALL_DIR" ]; then
    ngc registry resource download-version "nvidia/nemo-microservices/nemo-microservices-quickstart:$NEMO_TAG"
else
    echo "Directory exists, skipping download."
fi

cd "$INSTALL_DIR"

# --- 5. CONFIGURATION: CPU-ONLY MODE & ENV VARS ---
echo ">>> ⚙️ Applying 't3.large' fixes (CPU Mode)..."
sed -i '/driver: nvidia/d' docker-compose.yaml
sed -i '/runtime: nvidia/d' docker-compose.yaml

echo ">>> 📝 Generating .env configuration..."
cat <<EOF > .env
NEMO_MICROSERVICES_IMAGE_REGISTRY=nvcr.io/nvidia/nemo-microservices
NEMO_MICROSERVICES_IMAGE_TAG=$NEMO_TAG
NGC_API_KEY=$API_KEY
NIM_API_KEY=$API_KEY
EOF

# --- 5.5 INSTALL PYTHON YAML DEPENDENCY ---
sudo apt-get install -y python3-yaml

# --- 5.6 CONFIGURE UFW ---
if command -v ufw > /dev/null; then
    echo ">>> 🔓 Configuring UFW..."
    sudo ufw allow 8000/tcp
    sudo ufw allow 8080/tcp
    sudo ufw allow 3000/tcp
fi

# ============================================================
# KEY CHANGE: Create a boot-time script that patches the
# docker-compose.yaml with the CURRENT instance IP every
# time the instance starts — not just at AMI creation time.
# ============================================================

# --- 5.7 SAVE A CLEAN TEMPLATE OF docker-compose.yaml ---
echo ">>> 📋 Saving clean docker-compose template..."
cp docker-compose.yaml docker-compose.yaml.template

# --- 5.8 CREATE THE BOOT-TIME PATCHER SCRIPT ---
echo ">>> 🔧 Creating boot-time configuration patcher..."

cat <<'PATCHER_SCRIPT' > ${INSTALL_DIR}/patch-compose-config.sh
#!/bin/bash
# This script runs at EVERY BOOT before docker compose starts.
# It reads the CURRENT private IP and patches docker-compose.yaml.

set -e

INSTALL_DIR="__INSTALL_DIR__"
cd "$INSTALL_DIR"

# Always start from the clean template
cp docker-compose.yaml.template docker-compose.yaml

# Get the CURRENT private IP (works on any new EC2 instance)
# Method 1: EC2 Instance Metadata (most reliable on AWS)
HOST_IP=$(TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600") && \
    curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/local-ipv4)

# Fallback: parse from hostname -I
if [ -z "$HOST_IP" ]; then
    HOST_IP=$(hostname -I | awk '{print \$1}')
fi

echo ">>> 🌍 Current Host Private IP: $HOST_IP"

# Patch the compose file with the current IP
python3 - <<PYEOF
import yaml

HOST_IP = "${HOST_IP}"

compose_file = 'docker-compose.yaml'
with open(compose_file, 'r') as f:
    compose = yaml.safe_load(f)

# Expose port 3000 externally
for service_name, service in compose.get('services', {}).items():
    if 'ports' in service:
        if '3000:3000' not in service['ports']:
            service['ports'].append('3000:3000')

# Inject proxy registry configuration with CURRENT IP
config_str = compose['configs']['platform_config']['content']
config_data = yaml.safe_load(config_str)
proxy_registry = {
    'default': 'stateless_proxy',
    'providers': [{
        'name': 'stateless_proxy',
        'endpoint': f'http://{HOST_IP}:8000/proxy/v1',
        'api_key': 'NIM_API_KEY',
        'provider_type': 'openai'
    }]
}
if 'data_designer' not in config_data:
    config_data['data_designer'] = {}
config_data['data_designer']['model_provider_registry'] = proxy_registry

compose['configs']['platform_config']['content'] = yaml.dump(config_data)

with open(compose_file, 'w') as f:
    yaml.dump(compose, f, sort_keys=False)

print(f">>> ✅ docker-compose.yaml patched with IP: {HOST_IP}")
PYEOF
PATCHER_SCRIPT

# Replace placeholder with actual install dir
sed -i "s|__INSTALL_DIR__|${INSTALL_DIR}|g" ${INSTALL_DIR}/patch-compose-config.sh
chmod +x ${INSTALL_DIR}/patch-compose-config.sh

# Run it now for the first time
echo ">>> 🔧 Running initial configuration patch..."
bash ${INSTALL_DIR}/patch-compose-config.sh

# --- 6. CREATE SYSTEMD SERVICES ---
# 6a. Config patcher (runs before main service)
echo ">>> 🛡️ Creating Config Patcher Service..."
sudo bash -c "cat <<EOF > /etc/systemd/system/nemo-config-patcher.service
[Unit]
Description=NeMo Docker Compose Config Patcher (updates IP on boot)
Before=nemo-data-designer.service
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=ubuntu
ExecStart=/bin/bash ${INSTALL_DIR}/patch-compose-config.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF"

# 6b. Main NeMo service (depends on patcher)
echo ">>> 🛡️ Creating Main NeMo Service..."
SERVICE_FILE="/etc/systemd/system/nemo-data-designer.service"
sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=NVIDIA NeMo Data Designer Microservice
After=docker.service network-online.target nemo-config-patcher.service
Requires=docker.service nemo-config-patcher.service

[Service]
Type=simple
User=ubuntu
Group=docker
WorkingDirectory=$INSTALL_DIR
ExecStartPre=-/usr/bin/docker compose --profile data-designer down
ExecStart=/usr/bin/docker compose --profile data-designer up
ExecStop=/usr/bin/docker compose --profile data-designer down
Restart=always
RestartSec=10
EnvironmentFile=$INSTALL_DIR/.env

[Install]
WantedBy=multi-user.target
EOF"

# --- 7. ENABLE AND START ---
echo ">>> 🔌 Enabling and Starting Services..."
sudo systemctl daemon-reload
sudo systemctl enable nemo-config-patcher.service
sudo systemctl enable nemo-data-designer.service
sudo systemctl restart nemo-config-patcher.service
sudo systemctl restart nemo-data-designer.service

# --- 8. SMART WAIT LOOP ---
echo "----------------------------------------------------------------"
echo ">>> ⏳ Waiting for services to start (10-15 min on t3.large)..."
echo "----------------------------------------------------------------"

TIMEOUT=3600
ELAPSED=0
CHECK_INTERVAL=10

while [ $ELAPSED -lt $TIMEOUT ]; do
    if docker ps --format '{{.Names}}' | grep -q "nemo-microservices-data-designer"; then
        echo ""
        echo ">>> ✅ Container detected!"
        echo ">>> 🔍 Checking Health Status..."
        sleep 10
        break
    fi
    echo -ne ">>>    [${ELAPSED}s / ${TIMEOUT}s] Initializing... \r"
    sleep $CHECK_INTERVAL
    ELAPSED=$((ELAPSED+CHECK_INTERVAL))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo ""
    echo ">>> ❌ Timeout reached."
    echo ">>> Check logs: sudo journalctl -u nemo-data-designer -f"
    exit 1
fi

echo ""
echo "=========================================================="
echo "✅ DEPLOYMENT SUCCESSFUL"
echo "=========================================================="
docker ps
echo ""
echo "Config patcher status: sudo systemctl status nemo-config-patcher"
echo "Main service logs:     sudo journalctl -u nemo-data-designer -f"
echo "=========================================================="
