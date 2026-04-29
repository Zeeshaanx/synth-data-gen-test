from fastapi import APIRouter

router = APIRouter()

@router.get("/ok")
def health():
    return {"status": "ok"}
