# ================================================================
# BLOCK: APP_ENTRY
# Purpose: Mount routers + serve built SPA from app/static
# ================================================================
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from .db import engine, Base
from .api import tasks as tasks_router
from .api import students as students_router
from .api import users as users_router
from .api import misc as misc_router

app = FastAPI(title="Simple Task Pro API")

# CORS for local dev + demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB tables on start
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

# Routers
app.include_router(tasks_router.router)
app.include_router(students_router.router)
app.include_router(users_router.router)
app.include_router(misc_router.router)

# Serve built frontend (Render copies to app/static/)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
ASSETS_DIR = os.path.join(STATIC_DIR, "assets")
if os.path.isdir(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

@app.middleware("http")
async def no_cache_index(req: Request, call_next):
    resp: Response = await call_next(req)
    if req.url.path in ("/", "/index.html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp

@app.head("/")
def head_root():
    return Response(status_code=200)

@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if os.path.isdir(STATIC_DIR):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
    raise HTTPException(status_code=404, detail="Not found")
