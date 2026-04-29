import os
import json
from cryptography.fernet import Fernet

SERVER_SECRET_KEY = os.environ.get("PROXY_SECRET_KEY")
if not SERVER_SECRET_KEY:
    SERVER_SECRET_KEY = Fernet.generate_key()

cipher = Fernet(SERVER_SECRET_KEY)

def encrypt_auth_data(data: dict) -> str:
    json_bytes = json.dumps(data).encode('utf-8')
    return cipher.encrypt(json_bytes).decode('utf-8')

def decrypt_auth_data(token: str) -> dict:
    json_bytes = cipher.decrypt(token.encode('utf-8'))
    return json.loads(json_bytes.decode('utf-8'))
