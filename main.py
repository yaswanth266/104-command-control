import os
import datetime
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from app.api.routers import auth, tickets, dashboard, intake, users, meta
from app.core.config import WEB_DIR

app = FastAPI(title="104 Central Command Center")

app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(tickets.collection_router)
app.include_router(dashboard.router)
app.include_router(intake.router)
app.include_router(users.router)
app.include_router(meta.router)

@app.get("/health")
def health():
    return {"ok": True, "service": "ccc", "time": datetime.datetime.now().isoformat()}

@app.get("/")
def root():
    p = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(p):
        return FileResponse(p)
    return JSONResponse({"service": "ccc"})
