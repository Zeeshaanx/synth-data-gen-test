import httpx
from fastapi import HTTPException
from utils.encryption import decrypt_auth_data
from utils.adapters import adapt_anthropic_request, adapt_anthropic_response

async def handle_proxy_request(body: dict):
    tunnel_model = body.get("model", "")
    parts = tunnel_model.split("__")
    if len(parts) != 3: raise HTTPException(400, "Invalid tunnel")

    real_model, provider, token = parts
    
    try:
        auth = decrypt_auth_data(token)
        key, base_url, ver = auth["key"], auth.get("url"), auth.get("version")
    except: raise HTTPException(401, "Invalid Token")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    target = ""
    is_anthropic = False

    if provider == "openai": target = "https://api.openai.com/v1/chat/completions"
    elif provider == "nvidiabuild": target = "https://integrate.api.nvidia.com/v1/chat/completions"
    elif provider == "groq": target = "https://api.groq.com/openai/v1/chat/completions"
    elif provider == "google": target = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    elif provider == "microsoft":
        target = f"{base_url.rstrip('/')}/openai/deployments/{real_model}/chat/completions?api-version={ver or '2023-05-15'}"
        headers["api-key"] = key
        del headers["Authorization"]
    elif provider == "anthropic":
        target = "https://api.anthropic.com/v1/messages"
        headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
        del headers["Authorization"]
        is_anthropic = True
    elif provider == "custom":
        target = f"{base_url.rstrip('/')}/chat/completions"
    
    body["model"] = real_model
    req_body = adapt_anthropic_request(body) if is_anthropic else body

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(target, json=req_body, headers=headers)
        if resp.status_code >= 400: return httpx.Response(resp.status_code, content=resp.content)
        return adapt_anthropic_response(resp.json()) if is_anthropic else resp.json()
