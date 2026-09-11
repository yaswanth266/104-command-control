import os
from dotenv import load_dotenv
load_dotenv()

import asyncio
import datetime
import contextlib
from fastapi import FastAPI, APIRouter
from fastapi.responses import FileResponse, JSONResponse
from app.api.routers import auth, tickets, dashboard, intake, users, meta, notifications, health, admin, lookup, lt, reports
from app.core.config import WEB_DIR, UPLOAD_DIR
from app.core.middleware import RequestIdMiddleware
from app.services.sla_sweep import sla_sweep_loop
from app.services.master_sync import master_sync_loop

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [asyncio.create_task(sla_sweep_loop()), asyncio.create_task(master_sync_loop())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
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
api_router.include_router(admin.router)
api_router.include_router(lookup.router)
api_router.include_router(lt.router)
api_router.include_router(reports.router)

app.include_router(api_router)

@app.get("/health")
def health():
    return {"ok": True, "service": "ccc", "time": datetime.datetime.now().isoformat()}

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/")
def root():
    p = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(p):
        return FileResponse(p)
    return JSONResponse({"service": "ccc"})
