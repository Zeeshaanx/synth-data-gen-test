from fastapi import FastAPI
from contextlib import asynccontextmanager
from utils.patching import apply_patches
from routes import client_router, proxy_router, base_router, ui_router
import db

# 1. Apply Fixes
apply_patches()

# 2. Lifespan (startup / shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()   # connect to PostgreSQL (non-fatal if unavailable)
    yield
    await db.close_pool()

# 3. Init App
app = FastAPI(title="NeMo Data Designer SaaS API", lifespan=lifespan)

# 4. Include Routers
app.include_router(client_router.router)
app.include_router(proxy_router.router)
app.include_router(base_router.router)
app.include_router(ui_router.router)  # /home and /jobs UI pages
