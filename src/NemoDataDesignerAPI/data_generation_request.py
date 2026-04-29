import json
import requests
import pandas as pd
import time
import sys
from google.colab import userdata

# ==============================
# ⚙️ CONFIGURATION
# ==============================

BASE_URL = "http://98.92.244.42" # change this with your Base url
SERVICE_BASE_URL = f"{BASE_URL}/synth-data-gen/data_generation/v1"
CREATE_URL = f"{SERVICE_BASE_URL}/create"
JOBS_URL = f"{SERVICE_BASE_URL}/jobs"

NEMO_SERVICE_HEALTH_URL = f"{BASE_URL}:8080/v1/data-designer/jobs"

# 🤖 MODEL CONFIG
MODEL_PROVIDER = "nvidiabuild"
MODEL_ID = "qwen/qwen2.5-coder-32b-instruct"

# 🔑 API KEY
# Note: In production, use os.getenv() or userdata.get()
API_KEY = "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"

# ==============================
# 0️⃣ Wait for NeMo Service Health
# ==============================

print("🔍 Checking NeMo Data Designer health...")

max_retries = 60          # ~5 minutes (60 * 5s)
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

#time.sleep(300)
# ==============================
# 1️⃣ Build Generate Request
# ==============================

payload = {
    # --- SaaS Auth ---
    "model_provider": MODEL_PROVIDER,
    "model_id": MODEL_ID,
    "provider_api_key": API_KEY,

    # --- Job Settings ---
    "num_records": 5,
    "temperature": 0.8,
    "top_p": 0.95,
    "max_tokens": 1024,

    # ---- Sampler Columns ----
    "sampler_columns": [
        {
            "name": "topic",
            "sampler_type": "category",
            "params": {
                "values": ["Cybersecurity", "Artificial Intelligence", "Cloud Computing", "Blockchain"],
                "weights": [0.2, 0.4, 0.3, 0.1]
            }
        },
        {
            "name": "content_format",
            "sampler_type": "category",
            "params": {
                "values": ["Tweet", "LinkedIn Post", "Technical Blog Intro", "Email Subject Line"]
            }
        },
        {
            "name": "target_audience",
            "sampler_type": "category",
            "params": {
                "values": ["CTOs", "Junior Developers", "General Public"]
            }
        }
    ],

    # ---- LLM Text Columns ----
    "llm_text_columns": [
        {
            "name": "generated_content",
            "prompt": (
                "Write a {{ content_format }} about {{ topic }} targeting {{ target_audience }}. "
                "Keep it engaging and concise."
            )
        }
    ],

    # ---- LLM Structured Columns ----
    "llm_structured_columns": [
        {
            "name": "content_metadata",
            "prompt": "Analyze the generated content request for {{ topic }}.",
            "output_format": {
                "type": "object",
                "properties": {
                    "estimated_reading_time_seconds": {"type": "integer"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "sentiment": {"type": "string", "enum": ["Professional", "Casual", "Urgent"]}
                },
                "required": ["estimated_reading_time_seconds", "tags", "sentiment"]
            }
        }
    ],

    # ---- LLM Judge Columns ----
    "llm_judge_columns": [
        {
            "name": "content_quality_score",
            "prompt": "Evaluate this content: {{ generated_content }}",
            "scores": [
                {
                    "name": "relevance",
                    "description": "Does this content accurately match the topic {{ topic }}?",
                    "options": {
                        "High": "Perfect match",
                        "Medium": "Somewhat related",
                        "Low": "Off-topic"
                    }
                }
            ]
        }
    ]
}

# ==============================
# 2️⃣ Step 1: Submit Job
# ==============================

print(f"🚀 Sending Request to {CREATE_URL}...")
print(f"   Provider: {MODEL_PROVIDER}")
print(f"   Model: {MODEL_ID}")

try:
    # We send `generate_request` as a form field.
    # No files argument needed since we aren't using a seed file.
    response = requests.post(
        CREATE_URL,
        data={"generate_request": json.dumps(payload)},
        timeout=30
    )

    if response.status_code != 200:
        print(f"❌ Failed to submit job: {response.status_code}")
        print(response.text)
        exit(1)

    # Get Job ID
    data = response.json()
    job_id = data["job_id"]
    print(f"✅ Job Started! ID: {job_id}")
    print("⏳ Waiting for generation...")

    # ==============================
    # 3️⃣ Step 2: Poll for Results
    # ==============================

    start_time = time.time()

    while True:
        time.sleep(5) # Poll every 5 seconds

        status_resp = requests.get(f"{JOBS_URL}/{job_id}")

        if status_resp.status_code != 200:
            print(f"❌ Error checking status: {status_resp.text}")
            break

        job_data = status_resp.json()
        status = job_data["status"]
        elapsed = round(time.time() - start_time)

        # Print Status Line (Overwrite previous line)
        sys.stdout.write(f"\r   Status: {status.upper()} ({elapsed}s elapsed)")
        sys.stdout.flush()

        if status == "completed":
            print("\n\n✅ Generation SUCCESS!")
            result = job_data["result"]

            print(f"   Records: {result.get('num_records')}")
            print(f"   Time: {result.get('duration_seconds')}s")
            print(f"   CSV Path: {result.get('saved_csv_path')}")

            print("\n📊 Sample Output:")
            df = pd.DataFrame(result["dataset"])

            # Display specific columns
            cols_to_show = ["topic", "content_format", "generated_content", "content_quality_score"]
            # Handle case where columns might not exist if generation failed partially
            available_cols = [c for c in cols_to_show if c in df.columns]
            print(df[available_cols].head().to_string())
            break

        elif status == "failed":
            print(f"\n\n❌ Job Failed!")
            print(f"   Error: {job_data.get('error')}")
            break

except Exception as e:
    print(f"\n❌ Connection Error: {e}")
