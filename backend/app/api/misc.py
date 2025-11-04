# ================================================================
# BLOCK: MISC_ROUTER
# Purpose: /api/health + /api/me (demo header-based)
# ================================================================
from fastapi import APIRouter, Request

router = APIRouter(tags=["misc"])

@router.get("/api/health")
def health():
    return {"status": "ok"}

@router.get("/api/me")
def me(req: Request):
    # Send X-User: paddy / ulf / una  (demo)
    u = (req.headers.get("X-User") or "paddy").lower()
    if u == "paddy":
        return {"name": "Paddy MacGrath", "role": "Admin"}
    elif u == "ulf":
        return {"name": "Ulf", "role": "User"}
    else:
        return {"name": "Una", "role": "User"}
