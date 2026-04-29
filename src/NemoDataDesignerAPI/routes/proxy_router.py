from fastapi import APIRouter, Request, HTTPException
from controllers.proxy_controller import handle_proxy_request

router = APIRouter(prefix="/proxy/v1")

@router.get("/models")
async def list_models():
    return {"object": "list", "data": [{"id": "tunnel", "object": "model", "owned_by": "saas"}]}

@router.post("/chat/completions")
async def proxy_chat(request: Request):
    try:
        body = await request.json()
        return await handle_proxy_request(body)
    except Exception as e:
        raise HTTPException(502, f"Proxy Error: {e}")
    