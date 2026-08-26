import os
import asyncio
import datetime
import contextlib
from fastapi import FastAPI, APIRouter
from fastapi.responses import FileResponse, JSONResponse
from app.api.routers import auth, tickets, dashboard, intake, users, meta, notifications, health
from app.core.config import WEB_DIR
from app.core.middleware import RequestIdMiddleware
from app.services.sla_sweep import sla_sweep_loop

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(sla_sweep_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

app = FastAPI(title="104 Central Command Center", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)

api_router = APIRouter(prefix="/cccapi")
api_router.include_router(auth.router)
api_router.include_router(tickets.router)
api_router.include_router(tickets.collection_router)
api_router.include_router(dashboard.router)
api_router.include_router(intake.router)
api_router.include_router(users.router)
api_router.include_router(meta.router)
api_router.include_router(notifications.router)
api_router.include_router(health.router)

app.include_router(api_router)

@app.get("/health")
def health():
    return {"ok": True, "service": "ccc", "time": datetime.datetime.now().isoformat()}

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

@app.get("/")
def root():
    p = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(p):
        return FileResponse(p)
    return JSONResponse({"service": "ccc"})
