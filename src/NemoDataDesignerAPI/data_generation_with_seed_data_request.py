import json
import requests
import pandas as pd
import os
import time
import sys
from google.colab import userdata

# ==============================
# ⚙️ CONFIGURATION
# ==============================

# We separate the Base URL to easily construct the polling URL
BASE_URL = "http://3.238.72.235" # change this with your Base url
SERVICE_BASE_URL = f"{BASE_URL}:8000/data_generation/v1"
CREATE_URL = f"{SERVICE_BASE_URL}/create"
JOBS_URL = f"{SERVICE_BASE_URL}/jobs"

NEMO_SERVICE_HEALTH_URL = f"{BASE_URL}:8080/v1/data-designer/jobs"

SEED_FILE = "seed_customers.csv"

# 🔑 API KEY
USER_API_KEY = userdata.get('openai_key')

# 🤖 MODEL SELECTION
MODEL_PROVIDER = "nvidiabuild"
MODEL_ID = "qwen/qwen2.5-coder-32b-instruct"

time.sleep(60)
# ==============================
# 0️⃣ Wait for NeMo Service Health
# ==============================

print("🔍 Checking NeMo Data Designer health...")

max_retries = 600          # ~5 minutes (60 * 5s)
retry_delay = 5           # seconds

for attempt in range(1, max_retries + 1):
    try:
        health_resp = requests.get(NEMO_SERVICE_HEALTH_URL, timeout=5)

        if health_resp.status_code == 200:
            print("✅ NeMo Service is healthy and ready!")
            break

        else:
            print(f"   Attempt {attempt}: Service not ready (Status {health_resp.status_code})")

    except requests.exceptions.RequestException:
        print(f"   Attempt {attempt}: Unable to connect...")

    time.sleep(retry_delay)

else:
    print("❌ NeMo service did not become ready in time.")
    sys.exit(1)

# ==============================
# 1️⃣ Create Seed Dataset
# ==============================

seed_data = [
    {"first_name": "Alice", "last_name": "Johnson", "age": 29, "city": "New York"},
    {"first_name": "Bob", "last_name": "Smith", "age": 45, "city": "Chicago"},
    {"first_name": "Carol", "last_name": "Davis", "age": 34, "city": "San Francisco"},
    {"first_name": "David", "last_name": "Wilson", "age": 52, "city": "Miami"},
]

seed_df = pd.DataFrame(seed_data)
seed_df.to_csv(SEED_FILE, index=False)
print(f"✅ Seed dataset created: {SEED_FILE}")

# ==============================
# 2️⃣ Build Request Payload
# ==============================

payload = {
    # --- Auth & Routing ---
    "model_provider": MODEL_PROVIDER,
    "model_id": MODEL_ID,
    "provider_api_key": "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",

    # --- Job Settings ---
    "num_records": 5,
    "temperature": 0.7,
    "top_p": 1.0,
    "max_tokens": 1024,

    # ---- Columns (Same as before) ----
    "sampler_columns": [
        {
            "name": "product_category",
            "sampler_type": "category",
            "params": {"values": ["Electronics", "Clothing", "Books"], "weights": [0.4, 0.4, 0.2]}
        },
        {
            "name": "product_name_prefix",
            "sampler_type": "category",
            "params": {"values": ["Ultra", "Smart", "Eco", "Pro"]}
        },
        {
            "name": "user_role",
            "sampler_type": "category",
            "params": {"values": ["Admin", "Editor", "Viewer"]}
        },
        {
            "name": "industry",
            "sampler_type": "category",
            "params": {"values": ["FinTech", "HealthTech", "EdTech"]}
        }
    ],
    "expression_columns": [
        {"name": "full_name", "expr": "{{ first_name }} {{ last_name }}"},
        {"name": "sku_code", "expr": "{{ product_name_prefix }}-{{ product_category | replace(' ', '') }}-{{ range(100, 999) | random }}"}
    ],
    "llm_text_columns": [
        {
            "name": "customer_bio",
            "prompt": "Write a 1-sentence bio for {{ first_name }}, a {{ age }} year old living in {{ city }}."
        },
        {
            "name": "product_description",
            "prompt": "Write a product description for a {{ product_category }} item called '{{ product_name_prefix }} Widget'."
        }
    ],
    "llm_code_columns": [
        {
            "name": "data_processor_py",
            "prompt": "Write a Python function named `process_{{ industry | lower }}`.",
            "code_lang": "python"
        }
    ],
    "llm_structured_columns": [
        {
            "name": "user_metadata",
            "prompt": "Generate metadata for a {{ user_role }} user.",
            "output_format": {
                "type": "object",
                "properties": {
                    "access_level": {"type": "integer"},
                    "permissions": {"type": "array", "items": {"type": "string"}},
                    "is_active": {"type": "boolean"}
                },
                "required": ["access_level", "permissions", "is_active"]
            }
        }
    ],
    "llm_judge_columns": [
        {
            "name": "description_score",
            "prompt": "Rate the sales appeal of: {{ product_description }}",
            "scores": [
                {
                    "name": "sales_appeal",
                    "description": "Likelihood to buy",
                    "options": {"5": "High", "3": "Medium", "1": "Low"}
                }
            ]
        }
    ],
    "validation_columns": [
        {
            "name": "code_check",
            "target_columns": ["data_processor_py"],
            "validator_type": "code",
            "validator_params": {"code_lang": "python"}
        }
    ]
}

# ==============================
# 3️⃣ Step 1: Submit Job
# ==============================

print(f"🚀 Sending request to {CREATE_URL}...")

try:
    with open(SEED_FILE, "rb") as f:
        response = requests.post(
            CREATE_URL,
            files={"seed_data": (SEED_FILE, f, "text/csv")},
            data={"generate_request": json.dumps(payload)},
            timeout=30
        )

    if response.status_code != 200:
        print(f"❌ Failed to create job: {response.text}")
        exit(1)

    initial_response = response.json()
    job_id = initial_response["job_id"]
    print(f"✅ Job Created! ID: {job_id}")
    print("⏳ Waiting for generation to complete...")

    # ==============================
    # 4️⃣ Step 2: Poll for Results
    # ==============================

    start_time = time.time()

    while True:
        # Check status every 5 seconds
        time.sleep(5)

        status_response = requests.get(f"{JOBS_URL}/{job_id}")

        if status_response.status_code != 200:
            print(f"❌ Error checking status: {status_response.text}")
            break

        job_data = status_response.json()
        status = job_data["status"]

        # Calculate elapsed time
        elapsed = round(time.time() - start_time)
        sys.stdout.write(f"\r   Current Status: {status.upper()} ({elapsed}s elapsed)")
        sys.stdout.flush()

        if status == "completed":
            print("\n\n✅ Job Completed Successfully!")
            result = job_data["result"]

            print(f"   Records Generated: {result.get('num_records')}")
            print(f"   Duration: {result.get('duration_seconds')}s")

            # Load Data
            print("\n📊 Sample Output:")
            df = pd.DataFrame(result["dataset"])
            print(df.head(3).to_string())
            break

        elif status == "failed":
            print(f"\n\n❌ Job Failed!")
            print(f"   Error: {job_data.get('error')}")
            break

except Exception as e:
    print(f"\n\n❌ Connection Failed: {str(e)}")
