from config import COLUMN_CACHE
import nemo_microservices.data_designer.config.datastore as datastore_module
import nemo_microservices.data_designer.config.config_builder as config_builder_module

# Original Function
_original_fetch = datastore_module.fetch_seed_dataset_column_names

def patched_fetch_column_names(dataset_reference):
    try:
        repo_id = None
        if hasattr(dataset_reference, 'repo_id'):
            repo_id = dataset_reference.repo_id
        elif isinstance(dataset_reference, dict):
            repo_id = dataset_reference.get('repo_id')

        if repo_id and repo_id in COLUMN_CACHE:
            print(f"⚡ [Patch] Using cached columns for {repo_id}")
            return COLUMN_CACHE[repo_id]
    except Exception as e:
        print(f"⚠️ Patch warning: {e}")

    print(f"🌍 [Patch] Cache miss for {repo_id}, hitting network...")
    return _original_fetch(dataset_reference)

def apply_patches():
    datastore_module.fetch_seed_dataset_column_names = patched_fetch_column_names
    config_builder_module.fetch_seed_dataset_column_names = patched_fetch_column_names
    print("✅ Applied Monkey Patch for Seed Data")
