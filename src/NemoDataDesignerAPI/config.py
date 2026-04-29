import os
from pathlib import Path

# Network Cleanup
for key in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
    if key in os.environ: del os.environ[key]

os.environ["NO_PROXY"] = "localhost,127.0.0.1,0.0.0.0"
os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

# Service Config
FIXED_MODEL_ALIAS = "saas_generator"
BASE_IP = "127.0.0.1"
NEMO_MICROSERVICES_BASE_URL = f"http://{BASE_IP}:8080"
DATASTORE_ENDPOINT = f"http://{BASE_IP}:3000/v1/hf"

# Directories
UPLOAD_DIR = Path("uploaded_datasets")
UPLOAD_DIR.mkdir(exist_ok=True)

OUTPUT_DIR = Path("generated_output")
OUTPUT_DIR.mkdir(exist_ok=True)

# In-Memory Job Store (Replace with Redis in Prod)
JOB_STORE = {}
COLUMN_CACHE = {} # For Seed Data Patching
