import time

def adapt_anthropic_request(openai_body: dict):
    """
    Converts standard OpenAI 'messages' format to Anthropic's format.
    Extracts 'system' role to top-level parameter.
    """
    messages = []
    system_prompt = None
    
    for m in openai_body.get("messages", []):
        if m["role"] == "system":
            system_prompt = m["content"]
        else:
            messages.append({"role": m["role"], "content": m["content"]})
            
    payload = {
        "model": openai_body.get("model"),
        "messages": messages,
        "max_tokens": openai_body.get("max_tokens", 1024),
        "temperature": openai_body.get("temperature", 0.5),
    }
    
    if system_prompt:
        payload["system"] = system_prompt
        
    return payload

def adapt_anthropic_response(anthropic_resp: dict):
    """
    Converts Anthropic's response back to OpenAI format
    so NeMo understands it.
    """
    content = ""
    if "content" in anthropic_resp and len(anthropic_resp["content"]) > 0:
        content = anthropic_resp["content"][0]["text"]
        
    return {
        "id": anthropic_resp.get("id", "anthropic-id"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": anthropic_resp.get("model", "claude"),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": content
            },
            "finish_reason": "stop"
        }]
    }
