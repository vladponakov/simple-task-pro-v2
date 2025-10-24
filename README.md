# Simple Task Pro — v2 (P0 ready)

Fullstack demo:
- Backend: FastAPI + SQLite + SQLAlchemy with audit trail, soft delete, role visibility, status workflow.
- Frontend: minimal React to exercise P0 flows (English UI).

## Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
bash reset_seed.sh
uvicorn app.main:app --reload
```

## Frontend
```bash
cd frontend
npm i
npm run dev
```
Open http://localhost:5173

## Auth (demo)
Send header `X-User` with: `anna` (Admin), `ulf` (User 1), `una` (User 2).


---

## UI updates
- Mobile-friendly responsive grid (1–2–4 columns).
- Large, touch-friendly buttons.
- Modern color palette (violet/cyan gradient accents).
- **Drag & Drop** (Admin board): drop a task into a user column to Assign/Reassign; drop into Done to Complete.
- **Bulk actions**: Select multiple tasks → assign to Ulf/Una, complete, delete.
- **Filters**: text search, status, assignee.

Feature flags in `frontend/src/main.jsx`:
```js
const FLAGS = { dnd: true, bulk: true, filters: true, modernTheme: true }
```


## Google OAuth (optional, for real login + 2FA)
This demo ships with a **Login screen** supporting:
- **Demo login** (header `X-User`): Anna/Ulf/Una — no backend change.
- **Google Sign-In placeholder**: Enable real Google login by wiring OAuth to FastAPI.

Recommended approach:
1. Backend: add OAuth via `authlib` or `google-auth` (FastAPI) and store sessions/cookies.
2. Configure Google Cloud Console → OAuth 2.0 Client ID (Web).
3. Add allowed redirect URI: `http://localhost:8000/auth/callback`.
4. When authenticated, map Google account → internal `User` (role) and issue a session/JWT.
5. Frontend: load Google Identity script and call your `/auth/login/google` endpoint.

Note: 2FA is handled by **Google Account** itself. When you use Google OAuth, existing 2FA policies apply.

