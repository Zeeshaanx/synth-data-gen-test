import uuid
import shutil
import pandas as pd
from pathlib import Path
from fastapi import UploadFile
from config import UPLOAD_DIR, COLUMN_CACHE, DATASTORE_ENDPOINT, NEMO_MICROSERVICES_BASE_URL
from utils.encryption import encrypt_auth_data
from nemo_microservices.data_designer.essentials import NeMoDataDesignerClient

# Initialize Client for Seed Uploads
client = NeMoDataDesignerClient(base_url=NEMO_MICROSERVICES_BASE_URL)

def save_file_sync(file: UploadFile) -> Path:
    """
    Saves an uploaded file to disk synchronously.
    Used in Routers before offloading to background tasks.
    """
    if not file.filename.lower().endswith(".csv"):
        raise ValueError("Only CSV files are allowed")
        
    save_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    with open(save_path, "wb") as buffer:
        buffer.write(file.file.read())
    return save_path

def prepare_tunnel(req) -> str:
    """
    Encrypts API Key, Base URL, and Version into a secure token.
    Returns: MODEL__PROVIDER__ENCRYPTED_TOKEN
    """
    auth_payload = {
        "key": req.provider_api_key,
        "url": req.provider_base_url,
        "version": req.provider_api_version
    }
    encrypted_token = encrypt_auth_data(auth_payload)
    return f"{req.model_id}__{req.model_provider}__{encrypted_token}"

def process_seed_and_cache(file_path: Path):
    """
    1. Reads CSV columns to populate the Monkey Patch Cache.
    2. Uploads the file to NeMo Datastore.
    """
    try:
        # 1. Read columns locally to populate cache (Prevents Network Error)
        df = pd.read_csv(file_path, nrows=0)
        columns = df.columns.tolist()
        
        repo_id = f"data-designer/{file_path.stem}"
        
        # ⚡ POPULATE CACHE
        COLUMN_CACHE[repo_id] = columns
        print(f"✅ [Helper] Cached columns for {repo_id}: {columns}")

        # 2. Upload to Datastore
        print(f"🔄 [Helper] Uploading seed to {DATASTORE_ENDPOINT}...")
        return client.upload_seed_dataset(
            dataset=file_path,
            repo_id=repo_id,
            datastore_settings={"endpoint": DATASTORE_ENDPOINT},
        )
    except Exception as e:
        print(f"❌ Seed Processing Error: {e}")
        raise e
