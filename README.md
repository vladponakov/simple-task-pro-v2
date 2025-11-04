# Simple Task Pro — v2

Full-stack demo to automate end-to-end task assignment between **Admins** and **Teachers**, including task creation, delegation, execution, and audit tracking.

**Goal:** Automate workflows from A→™, enabling Admins to assign tasks to teachers, monitor progress, and collect results through API or manual input.

**Tech Stack:**
- **Backend:** FastAPI + SQLAlchemy + SQLite + Pydantic v2 + Uvicorn
- **Frontend:** React (Vite)
- **Deployment:** Render.com (CI/CD demo branch)

> Demo users (via header `X-User`):
> - **paddy** (Admin)
> - **ulf** (Teacher 1)
> - **una** (Teacher 2)

---

## 1. Local Development (Test Branch)

### Backend Setup
```bash
cd backend
python -m venv .venv
# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```
Access the API at **http://localhost:8000**

### Database Seeding
Seed demo data (users, students, tasks):
```bash
# Minimal dataset (safe)
python -m app.seed --ensure

# Full reset + demo data
python -m app.seed --reset

# Large dataset for stress testing (e.g., 100 students)
python -m app.seed --reset --big 100
```
SQLite database path: `/backend/app.db` (automatically created).

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Access UI at **http://localhost:5173**

#### Vite Proxy (for local dev)
`frontend/vite.config.js` automatically proxies API requests from `/api/*` → `http://localhost:8000` to avoid CORS.

---

## 2. Render Demo (Demo Branch)

### Build & Deploy Pipeline
Render runs the following build steps:
```bash
pip install -r requirements.txt
cd ../frontend
npm ci && npm run build
cd ../backend
mkdir -p app/static && rm -rf app/static/*
cp -r ../frontend/dist/* app/static/
```
Then starts the app:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Pre-deploy Seeding (Render)
`render.yaml` executes:
```bash
mkdir -p /data/tasks_feed
test -f /data/tasks_feed/tasks.csv || echo "student_id,title,address,due_at,assignee_user_id,status,reason" > /data/tasks_feed/tasks.csv
python -m app.seed --reset
```

> Replace `--reset` with `--ensure` to preserve data across deploys.

### Render Shell Checks
```bash
curl -sS https://demo-taskpro.onrender.com/api/health
# -> {"status":"ok"}

curl -sS -H "X-User: paddy" https://demo-taskpro.onrender.com/api/tasks | jq 'length'
# -> 4

python -m app.seed --reset   # manually reseed DB
```

---

## 3. API Overview

### Health & Identity
- `GET /api/health` → API OK
- `GET /api/me` → Returns current user (based on header)

### Tasks
- `GET /api/tasks` → list all tasks (Admin) or own tasks (User)
- `POST /api/tasks` (Admin) → create task
- `PATCH /api/tasks/{id}` → update task (restricted by role)
- `POST /api/tasks/{id}/assign` (Admin) → assign or reassign task
- `POST /api/tasks/{id}/status` → change status (`accept`, `reject`, `complete`)
- `DELETE /api/tasks/{id}` (Admin) → soft delete
- `POST /api/tasks/{id}/restore` → restore deleted task
- `GET /api/tasks/{id}/events` → list audit log

### Students
- `GET /api/students` → list students
- `POST /api/students` (Admin) → create student
- `GET /api/students/{id}/history` → absence + visit history

### Comments
- `GET /api/tasks/{id}/comments`
- `POST /api/tasks/{id}/comments`

---

## 4. Testing & Data Validation

### Quick API Test (Local)
```bash
curl -sS -H "X-User: paddy" http://localhost:8000/api/health
curl -sS -H "X-User: paddy" http://localhost:8000/api/tasks | jq 'length'
```

### DB Schema Checks (SQLite)
```bash
sqlite3 backend/app.db ".tables"
sqlite3 backend/app.db ".schema tasks"
```

---

## 5. Frontend UI Summary

### Features
- Responsive grid layout (1–2–4 columns)
- **Drag & Drop** task assignment (Admin)
- **Bulk Actions** (assign, complete, delete)
- **Filters** (text, status, assignee)
- **Audit Trail** per task
- **Comment system**

### Key Components
| Component | Function |
|------------|-----------|
| `TaskCard.jsx` | Displays individual task details & actions |
| `EditReasonModal.jsx` | Modal for task edit reason |
| `RejectReasonModal.jsx` | Modal for rejection reason |
| `text.ts` | Text utility helpers |
| `vite.config.js` | Proxy + build config |

---

## 6. Adding Test Data (Render or Local)

**Via Seeder (Recommended):**
```bash
python -m app.seed --ensure   # Safe
python -m app.seed --reset    # Drop & recreate
python -m app.seed --reset --big 80  # Large dataset
```

**Manual Insert:**
```bash
python - <<'PY'
from app.db import SessionLocal
from app.models import Task, TaskStatus
from datetime import datetime, timedelta
with SessionLocal() as s:
    t = Task(student_id=1, title="Ad-hoc visit", address="221B Baker St",
             due_at=datetime.utcnow()+timedelta(hours=2),
             status=TaskStatus.NEW, created_by=1)
    s.add(t); s.commit(); s.refresh(t)
    print("Created task", t.id)
PY
```

---

## 7. Connection Checks

**Backend → DB:** Tables auto-created by `Base.metadata.create_all()`

**Frontend → Backend (Dev):** Vite proxy handles CORS.

**Frontend (Render):** Static assets in `/app/static` and `/assets`. SPA fallback ensures `index.html` serves on unknown routes.

---

## 8. Purpose and Testing Story

The application is designed to automate the **assignment and follow-up process** between admins and teachers:
- **Admins** create, assign, and monitor tasks.
- **Teachers** accept, reject (with reason), or complete tasks.
- **Audit trail** and **comments** document each action.
- **APIs** can be integrated to automatically create or update tasks from external systems (e.g., attendance tracking, external DB feeds).

### Testing Goal
Validate that:
1. Admin can create and assign tasks to teachers.
2. Teachers can update and complete assigned tasks.
3. Data persists correctly and is reflected in audit logs.
4. API integrations can inject and sync task data programmatically.

---

## 9. Branch & Deployment Workflow

**Merge Demo → Test**
```bash
git fetch origin
git switch test
git merge origin/demo --no-edit
git push origin test
```

**Merge Test → Main (Production)**
```bash
git fetch origin
git switch main
git merge origin/test --no-edit
git push origin main
```

---

## 10. Troubleshooting

| Issue | Fix |
|--------|------|
| **Port 5173 already in use** | `npx vite --port 5174` |
| **CORS error** | Use `vite.config.js` proxy or `allow_origins` in FastAPI |
| **Missing /assets/** | Ensure build step copies `dist/*` to `app/static/` |
| **No tasks in UI** | Ensure header `X-User` is set (`localStorage.user = 'paddy'`) |
| **Health endpoint fails** | Check `uvicorn app.main:app --reload` running |

---