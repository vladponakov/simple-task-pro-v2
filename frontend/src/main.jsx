import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

/* ================================================================
   BLOCK: API_HELPERS
   Purpose: Base API helper + integration helpers for Make.com (prep)
   ================================================================= */
const isProd =
  typeof window !== "undefined" && !window.location.origin.includes("localhost");
const API_BASE = isProd ? "" : (import.meta.env?.VITE_API_BASE ?? "http://localhost:8000");

const API = (path, opts = {}) => {
  const p = path.startsWith("/api") ? path : `/api${path.startsWith("/") ? "" : "/"}${path}`;
  return fetch(`${API_BASE}${p}`, {
    headers: {
      "X-User": localStorage.getItem("user") || "paddy",
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
    cache: "no-store",
    ...opts,
  }).then(async (r) => {
    if (!r.ok) {
      try {
        const j = await r.json();
        if (j?.detail) throw new Error(j.detail);
      } catch {}
      throw new Error((await r.text()) || "Request failed");
    }
    return r.json();
  });
};

// Make.com prep (not used yet, but ready)
export const API_EXT = {
  createTask: (data) =>
    API("/api/tasks", { method: "POST", body: JSON.stringify(data) }),
  getDoneTasks: (since) =>
    API(`/api/tasks?status=Done${since ? `&updated_after=${encodeURIComponent(since)}` : ""}`),
};
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: UTILITIES
   Purpose: Small helpers used across components
   ================================================================= */
const onlyDateStr = (d) => {
  try {
    const dt = new Date(d);
    return isNaN(dt) ? null : dt.toISOString().slice(0, 10);
  } catch {
    return null;
  }
};

const fmtNO = (iso) =>
  iso
    ? new Date(iso).toLocaleString("no-NO", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "-";

const toIso = (v) => {
  if (!v) return null;
  const s = typeof v === "string" ? v.replace(" ", "T") : v;
  const d = new Date(s);
  return isNaN(d) ? null : d.toISOString();
};

const defaultDueAt = () => new Date().toISOString();

function buildSmartRouteUrl(addresses) {
  if (!addresses || addresses.length === 0) return null;
  const enc = (s) => encodeURIComponent(s || "London");
  if (addresses.length === 1) {
    return `https://www.google.com/maps/dir/?api=1&destination=${enc(addresses[0])}`;
  }
  const dest = enc(addresses[addresses.length - 1]);
  const waypoints = addresses.slice(0, -1).map(enc).join("|");
  return `https://www.google.com/maps/dir/?api=1&travelmode=driving&destination=${dest}&waypoints=${waypoints}`;
}

const titleCase = (s) =>
  (s || "")
    .toString()
    .replace(/\w\S*/g, (t) => t[0].toUpperCase() + t.slice(1).toLowerCase())
    .trim();

const getReason = (t) =>
  (
    t?.body ??
    t?.reason ??
    t?.reject_reason ??
    t?.rejection_reason ??
    t?.last_reason ??
    ""
  )
    .toString()
    .trim();

const USERS = [
  { id: 1, name: "Paddy MacGrath (Admin)" },
  { id: 2, name: "Ulf (User 1)" },
  { id: 3, name: "Una (User 2)" },
];
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: LOGIN
   Purpose: Simple demo login without exposing creds in UI
   ================================================================= */
function Login({ onDemoLogin, onGoogleLogin }) {
  const DEMO_PW = { paddy: "admin123", ulf: "user1", una: "user2" };

  const [who, setWho] = useState("paddy");
  const [pw, setPw] = useState("");

  const login = () => {
    if ((DEMO_PW[who] || "") !== pw.trim()) {
      alert("Invalid username or password.");
      return;
    }
    onDemoLogin(who);
    window.location.replace("/");
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="brand-top">
          <div className="brand-title">Simple Task Pro</div>
          <div className="brand-sub">Sign in to continue</div>
        </div>

        <div className="field">
          <label className="label">Username</label>
          <div className="input-wrap">
            <span className="prefix">👤</span>
            <input
              className="input bare"
              value={who}
              onChange={(e) => setWho(e.target.value)}
              placeholder="your.username"
            />
          </div>
        </div>

        <div className="field">
          <label className="label">Password</label>
          <div className="input-wrap">
            <span className="prefix">🔒</span>
            <input
              type="password"
              className="input bare"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              placeholder="••••••••"
            />
          </div>
        </div>

        <button className="btn btn-primary wide" onClick={login}>
          Sign in
        </button>

        <div className="divider">or</div>
        <button className="btn btn-google wide" onClick={onGoogleLogin}>
          <span className="gdot red" /> <span className="gdot yellow" /> <span className="gdot green" /> Continue with Google
        </button>
      </div>
    </div>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: HEADER + DRAWER
   Purpose: Topbar + Hamburger drawer (admin-only actions inside)
   ================================================================= */
function Header({ onOpenSmartRoute, todaysCount, onCreate, isAdmin }) {
  const [me, setMe] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    API("/api/me").then(setMe).catch(() => {});
  }, []);

  // Allow "Overview" button to open drawer from anywhere
  useEffect(() => {
    const open = () => setDrawerOpen(true);
    document.addEventListener("open-drawer", open);
    return () => document.removeEventListener("open-drawer", open);
  }, []);

  const initials = (me?.name || "User")
    .split(" ")
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <>
      <div className="app-header">
        <button
          className={`hamburger ${drawerOpen ? "open" : ""}`}
          onClick={() => setDrawerOpen((v) => !v)}
          aria-label="Open menu"
        >
          <span />
        </button>
        <div className="app-title">Simple Task Pro</div>
        <div className="spacer" />
        <button className="btn btn-primary" style={{ marginLeft: 8 }} onClick={onOpenSmartRoute}>
          Smart Route (today){todaysCount ? ` • ${todaysCount}` : ""}
        </button>
      </div>

      <div
        className={drawerOpen ? "drawer-backdrop open" : "drawer-backdrop"}
        onClick={() => setDrawerOpen(false)}
      />
      <aside
        className={drawerOpen ? "drawer open" : "drawer"}
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <strong>Menu</strong>
          <button className="btn" onClick={() => setDrawerOpen(false)}>
            Close
          </button>
        </header>

        <div className="userbox">
          <div className="avatar">{initials}</div>
          <div className="meta">
            <div className="name">{me ? me.name : "—"}</div>
            <div className="rolepill">{me ? me.role : ""}</div>
          </div>
        </div>

        {/* ============================================================
           BLOCK: HEADER_DRAWER_MENU
           Purpose: Drawer menu items; admin-only management actions
           ============================================================ */}
        <div className="menu">
          {/* New Task (admin only) */}
          {isAdmin && (
            <button
              className="mitem mitem--action"
              onClick={() => {
                setDrawerOpen(false);
                onCreate();
              }}
            >
              New task
            </button>
          )}

          {/* Admin management */}
          {isAdmin && (
            <>
              <button
                className="mitem mitem--action"
                onClick={async () => {
                  const name = prompt("Student name:");
                  if (!name?.trim()) return;
                  try {
                    await API("/api/students", {
                      method: "POST",
                      body: JSON.stringify({ name: name.trim() }),
                    });
                    alert("Student created.");
                  } catch (e) {
                    alert(e?.message || "Failed to create student");
                  }
                }}
              >
                Create student
              </button>

              <button
                className="mitem mitem--action"
                onClick={async () => {
                  const email = prompt("User email:");
                  const name = prompt("User name:");
                  if (!email?.trim() || !name?.trim()) return;
                  try {
                    await API("/api/users", {
                      method: "POST",
                      body: JSON.stringify({ email: email.trim(), name: name.trim() }),
                    });
                    alert("User created.");
                  } catch (e) {
                    alert(e?.message || "Failed to create user");
                  }
                }}
              >
                Create user
              </button>

              <button
                className="mitem mitem--danger"
                onClick={async () => {
                  const id = prompt("Student ID to delete:");
                  if (!id) return;
                  if (!confirm(`Delete student #${id}?`)) return;
                  try {
                    await API(`/api/students/${id}`, { method: "DELETE" });
                    alert("Student deleted.");
                  } catch (e) {
                    alert(e?.message || "Failed to delete student");
                  }
                }}
              >
                Delete student
              </button>

              <button
                className="mitem mitem--danger"
                onClick={async () => {
                  const id = prompt("User ID to delete:");
                  if (!id) return;
                  if (!confirm(`Delete user #${id}?`)) return;
                  try {
                    await API(`/api/users/${id}`, { method: "DELETE" });
                    alert("User deleted.");
                  } catch (e) {
                    alert(e?.message || "Failed to delete user");
                  }
                }}
              >
                Delete user
              </button>
            </>
          )}

          <button
            className="mitem"
            onClick={() => {
              setDrawerOpen(false);
              onOpenSmartRoute();
            }}
          >
            Open Smart Route
          </button>

          <button className="mitem" onClick={() => alert("Settings coming soon")}>
            Settings
          </button>

          <button
            className="mitem mitem--danger"
            onClick={() => {
              localStorage.removeItem("user");
              window.location.replace("/login");
            }}
          >
            Logout
          </button>
        </div>
        {/* ========================= END BLOCK ======================== */}
      </aside>
    </>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: COMMENTS
   Purpose: Simple comments list for a task
   ================================================================= */
function TaskComments({ taskId }) {
  const [comments, setComments] = useState([]);
  const [text, setText] = useState("");

  const load = () =>
    API(`/api/tasks/${taskId}/comments`)
      .then(setComments)
      .catch(() => setComments([]));

  useEffect(() => {
    load();
  }, [taskId]);

  const add = async () => {
    const val = text.trim();
    if (!val) return;
    await API(`/api/tasks/${taskId}/comments`, {
      method: "POST",
      body: JSON.stringify({ text: val }),
    });
    setText("");
    load();
  };

  return (
    <div className="card" style={{ marginTop: 10 }}>
      <strong>Comments</strong>
      <ul style={{ marginTop: 8 }}>
        {comments.map((c) => (
          <li key={c.id} style={{ marginBottom: 6, color: "var(--muted)" }}>
            <span style={{ opacity: 0.8 }}>{c.author || "User"}</span>{" "}
            <span style={{ opacity: 0.7 }}>
              • {new Date(c.created_at).toLocaleString("no-NO")}
            </span>
            <div>{c.text}</div>
          </li>
        ))}
      </ul>
      <div className="row" style={{ gap: 8, marginTop: 8 }}>
        <input
          className="input"
          placeholder="Write a comment…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button className="btn btn-primary" onClick={add}>
          Add
        </button>
      </div>
    </div>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: HISTORY_MODAL
   Purpose: Show student's absence/visit history
   ================================================================= */
function HistoryModal({ studentId, onClose }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    API(`/api/students/${studentId}/history`)
      .then(setItems)
      .catch(() => setItems([]));
  }, [studentId]);

  useEffect(() => {
    const onEsc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Student history</h3>
        <div className="mt-1" style={{ opacity: 0.8 }}>
          Absences / Visits
        </div>
        <ul className="mt-1">
          {items.map((it, i) => (
            <li key={i} style={{ margin: "6px 0", color: "var(--muted-700)" }}>
              {new Date(it.date || it.created_at).toLocaleString("no-NO")} —{" "}
              {it.type || it.note || it.status || "event"}
            </li>
          ))}
        </ul>
        <div className="btns" style={{ marginTop: 12 }}>
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: CREATE_MODAL
   Purpose: Create a new task (admin-triggered)
   ================================================================= */
function CreateModal({ defaultAssigneeId = 2, onClose, onCreated }) {
  const [students, setStudents] = useState([]);
  const [studentId, setStudentId] = useState("");
  const [title, setTitle] = useState("");
  const [address, setAddress] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    API("/api/students").then(setStudents).catch(() => setStudents([]));
  }, []);

  useEffect(() => {
    const onEsc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onEsc);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onEsc);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const createTask = async () => {
    if (!studentId) {
      setErr("Please select a student");
      return;
    }
    if (!title.trim()) {
      setErr("Title is required");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      await API(`/api/tasks`, {
        method: "POST",
        body: JSON.stringify({
          student_id: Number(studentId),
          title: title.trim(),
          address: address.trim() || null,
          body: reason ? reason.trim() : null,
          due_at: defaultDueAt(),
          assignee_user_id: defaultAssigneeId,
          status: "Assigned",
          checklist: [],
          external_ref: null,
        }),
      });
      await onCreated();
      onClose();
    } catch (e) {
      setErr(e?.message || "Failed to create");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>New Task</h3>
        {err && <div className="alert error">{err}</div>}

        <label className="label">Student</label>
        <select
          className="select"
          value={studentId}
          onChange={(e) => setStudentId(e.target.value)}
        >
          <option value="">Select…</option>
          {students.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>

        <label className="label">Title</label>
        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />

        <label className="label">Address</label>
        <input className="input" value={address} onChange={(e) => setAddress(e.target.value)} />

        <label className="label">Reason</label>
        <textarea
          className="textarea"
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />

        <div className="meta" style={{ marginTop: 8, opacity: 0.8 }}>
          {new Date().toLocaleString("no-NO")}
        </div>

        <div className="btns" style={{ marginTop: 12 }}>
          <button className="btn" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={createTask} disabled={saving}>
            {saving ? "Creating..." : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: EDIT_MODAL
   Purpose: Edit existing task, assign, delete (admin allowed)
   ================================================================= */
function EditModal({ task, onClose, onSaved, isAdmin }) {
  const [title, setTitle] = useState(task.title);
  const [address, setAddress] = useState(task.address || "");
  const [dueAt, setDueAt] = useState(task.due_at || defaultDueAt());
  const [reason, setReason] = useState(getReason(task));
  const [assignee, setAssignee] = useState(task.assignee_user_id || 2);

  const [checklist, setChecklist] = useState(Array.isArray(task.checklist) ? task.checklist : []);
  const [newItem, setNewItem] = useState("");

  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    const onEsc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onEsc);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onEsc);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const addItem = () => {
    const t = newItem.trim();
    if (!t) return;
    setChecklist([...checklist, { text: t, done: false }]);
    setNewItem("");
  };
  const toggleItem = (idx) => {
    const copy = checklist.slice();
    copy[idx] = { ...copy[idx], done: !copy[idx].done };
    setChecklist(copy);
  };
  const removeItem = (idx) => {
    const copy = checklist.slice();
    copy.splice(idx, 1);
    setChecklist(copy);
  };

  const payloadBase = {
    title,
    address: address || null,
    due_at: toIso(dueAt) || null,
    reason: reason || null, // server maps reason -> body
    checklist,
    external_ref: task.external_ref ?? null,
  };
  if (isAdmin) payloadBase.assignee_user_id = Number(assignee);

  const save = async () => {
    setSaving(true);
    setErr("");
    try {
      await API(`/api/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify(payloadBase),
      });
      await onSaved();
      onClose();
    } catch (e) {
      setErr(e?.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const saveAndAssign = async () => {
    setSaving(true);
    setErr("");
    try {
      await API(`/api/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify(payloadBase),
      });
      await API(`/api/tasks/${task.id}/assign`, {
        method: "POST",
        body: JSON.stringify({ assignee_user_id: Number(assignee) }),
      });
      await onSaved();
      onClose();
    } catch (e) {
      setErr(e?.message || "Failed to save & assign");
    } finally {
      setSaving(false);
    }
  };

  const deleteTask = async () => {
    if (!confirm("Delete this task?")) return;
    try {
      await API(`/api/tasks/${task.id}`, { method: "DELETE" });
      await onSaved();
      onClose();
    } catch (e) {
      alert(e?.message || "Failed to delete");
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="row" style={{ alignItems: "center", marginBottom: 8 }}>
          <h3 style={{ margin: 0, flex: 1 }}>Edit task</h3>
          <button
            className="btn"
            onClick={onClose}
            aria-label="Close"
            title="Close"
            style={{ padding: "6px 10px", lineHeight: 1, fontWeight: 700, borderRadius: 8 }}
          >
            ×
          </button>
        </div>

        {err && <div className="alert error">{err}</div>}

        <label className="label">Title</label>
        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />

        <label className="label">Address</label>
        <input className="input" value={address} onChange={(e) => setAddress(e.target.value)} />

        <label className="label">Due (yyyy-mm-dd hh:mm)</label>
        <input className="input" value={dueAt || ""} onChange={(e) => setDueAt(e.target.value)} />

        <label className="label">Reason</label>
        <textarea
          className="textarea"
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />

        <div className="card" style={{ marginTop: 10 }}>
          <strong>Checklist</strong>
          <ul style={{ marginTop: 8 }}>
            {checklist.map((it, i) => (
              <li key={i} className="row" style={{ gap: 8 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
                  <input type="checkbox" checked={!!it.done} onChange={() => toggleItem(i)} />
                  <input
                    className="input"
                    value={it.text}
                    onChange={(e) => {
                      const copy = checklist.slice();
                      copy[i] = { ...copy[i], text: e.target.value };
                      setChecklist(copy);
                    }}
                  />
                </label>
                <button className="btn btn-danger" onClick={() => removeItem(i)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <div className="row" style={{ gap: 8, marginTop: 8 }}>
            <input
              className="input"
              placeholder="Add checklist item…"
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
            />
            <button className="btn" onClick={addItem}>
              Add
            </button>
          </div>
        </div>

        {isAdmin && (
          <div className="row" style={{ gap: 8, marginTop: 10 }}>
            <label className="label" style={{ margin: 0 }}>
              Assign to
            </label>
            <select className="select" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
              {USERS.filter((u) => u.id !== 1).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="btns" style={{ marginTop: 12, gap: 8, flexWrap: "wrap" }}>
          <button className="btn" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button className="btn" onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </button>
          {isAdmin && (
            <button className="btn btn-primary" onClick={saveAndAssign} disabled={saving}>
              {saving ? "Working…" : "Save & Assign"}
            </button>
          )}
          {isAdmin && (
            <button className="btn btn-danger" onClick={deleteTask} disabled={saving}>
              Delete
            </button>
          )}
        </div>

        <TaskComments taskId={task.id} />
      </div>
    </div>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: DATA_HOOK
   Purpose: Load tasks list and expose reload()
   ================================================================= */
function useTasks() {
  const [tasks, setTasks] = useState([]);
  const reload = async () => {
    try {
      setTasks(await API("/api/tasks"));
    } catch {
      setTasks([]);
    }
  };
  useEffect(() => {
    reload();
  }, []);
  return { tasks, reload };
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: SEARCH_BAR
   Purpose: Compact, mobile-friendly search field
   ================================================================= */
function SearchBar({ value, onChange, placeholder = "Search tasks..." }) {
  const [t, setT] = useState(value || "");
  useEffect(() => {
    const id = setTimeout(() => onChange?.(t.trim()), 150);
    return () => clearTimeout(id);
  }, [t, onChange]);
  return (
    <div className="stp-searchbar">
      <input
        className="stp-searchbar__input"
        type="search"
        value={t}
        onChange={(e) => setT(e.target.value)}
        placeholder={placeholder}
        aria-label="Search tasks"
      />
    </div>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: TASK_CARD + COLUMN
   Purpose: Per-task UI with swipe (Done/Reject/Delete), History, Route today
   ================================================================= */
function TaskCard({ t, reload, compact, meId, isAdmin }) {
  const act = async (action, reason) => {
    try {
      await API(`/api/tasks/${t.id}/status`, {
        method: "POST",
        body: JSON.stringify({ action, reason }),
      });
      if (action === "reject") t.body = (reason || "").toString();
      if (action === "complete") {
        document.dispatchEvent(new CustomEvent("task-synced", { detail: { id: t.id, status: "Done" } }));
      }
      await reload();
    } catch (e) {
      alert(e?.message || "Failed to update task");
    }
  };

  const canEdit = isAdmin || t.assignee_user_id === meId;
  const reasonText = titleCase(getReason(t));

  // Touch swipe
  const startX = useRef(null);
  const [dragX, setDragX] = useState(0);
  const onTs = (e) => { startX.current = e.touches[0].clientX; };
  const onTm = (e) => {
    if (startX.current == null) return;
    setDragX(e.touches[0].clientX - startX.current);
  };
  const onTe = async () => {
    const th = 80;
    if (dragX > th) {
      await act("complete");
    } else if (dragX < -th) {
      if (isAdmin) {
        if (confirm("Delete this task?")) {
          try {
            await API(`/api/tasks/${t.id}`, { method: "DELETE" });
            await reload();
          } catch (e) {
            alert(e?.message || "Delete failed");
          }
        }
      } else {
        const r = prompt("Reject reason?");
        if (r) await act("reject", r);
      }
    }
    setDragX(0);
    startX.current = null;
  };

  return (
    <div
      className={`task ${compact ? "compact" : ""} ${t.status === "Rejected" ? "rejected" : ""}`}
      style={{ transform: `translateX(${dragX}px)` }}
      onTouchStart={onTs}
      onTouchMove={onTm}
      onTouchEnd={onTe}
    >
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="title">{t.title}</div>
        <div className="row" style={{ gap: 6 }}>
          {!!t.external_ref && <small className="badge">API</small>}
          <small className={`badge ${t.status === "Rejected" ? "rejected" : ""}`}>{t.status}</small>
        </div>
      </div>

      {!!reasonText && (
        <div className="mt-1">
          <div className="reason-label">REASON</div>
          <div className={`reason-text ${t.status === "Rejected" ? "red" : ""}`}>{reasonText}</div>
        </div>
      )}

      <div className="meta">
        {fmtNO(t.due_at)} • Address: {t.address || "-"}
      </div>

      <div className="btns">
        <button
          className="btn"
          onClick={() =>
            window.open(
              `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(t.address || "London")}`,
              "_blank"
            )
          }
        >
          Open in Maps
        </button>

        <button
          className="btn"
          onClick={() => document.dispatchEvent(new CustomEvent("open-history", { detail: { studentId: t.student_id } }))}
        >
          History
        </button>

        {!isAdmin && (
          <button
            className="btn"
            onClick={async () => {
              const r = prompt("Reject reason?");
              if (!r) return;
              await act("reject", r);
            }}
          >
            Reject
          </button>
        )}

        {!isAdmin && (
          <button
            className="btn"
            onClick={async () => {
              try {
                const today = new Date();
                today.setHours(9, 0, 0, 0);
                await API(`/api/tasks/${t.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({ due_at: today.toISOString(), external_ref: t.external_ref ?? null }),
                });
                await reload();
              } catch (e) {
                alert(e?.message || "Failed to set to today's route");
              }
            }}
          >
            Route today
          </button>
        )}

        <button className="btn btn-primary" onClick={() => act("complete")}>
          DONE
        </button>

        {canEdit && (
          <button
            className="btn"
            onClick={() => window.dispatchEvent(new CustomEvent("edit-task", { detail: { task: t } }))}
          >
            Edit
          </button>
        )}
      </div>
    </div>
  );
}

function Column({ title, filter, tasks, reload, compact, meId, isAdmin }) {
  const list = tasks.filter(filter);
  return (
    <div className="col">
      <h3>{title}</h3>
      <div className="drop-hint">Drop here</div>
      {list.map((t) => (
        <TaskCard key={t.id} t={t} reload={reload} compact={compact} meId={meId} isAdmin={isAdmin} />
      ))}
    </div>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: ADMIN_BOARD / USER_BOARD
   Purpose: Main board with filters + global search
   ================================================================= */
function AdminBoard({ compact, tasks, reload, isAdmin, meId, query }) {
  const text = (query || "").toLowerCase();
  const tasksTextFiltered = useMemo(() => {
    if (!text) return tasks;
    return tasks.filter((t) => {
      const hay = `${t.title || ""} ${t.body || ""} ${t.address || ""}`.toLowerCase();
      return hay.includes(text);
    });
  }, [tasks, text]);

  // USER VIEW
  if (!isAdmin) {
    const [scope, setScope] = useState("today");
    const todayStr = new Date().toISOString().slice(0, 10);
    const forMe = useMemo(() => tasksTextFiltered.filter((t) => t.assignee_user_id === meId), [tasksTextFiltered, meId]);
    const filtered = useMemo(() => {
      switch (scope) {
        case "today":
          return forMe.filter((t) => onlyDateStr(t.due_at) === todayStr && t.status !== "Done");
        case "upcoming":
          return forMe.filter((t) => onlyDateStr(t.due_at) > todayStr && t.status !== "Done");
        case "done":
          return forMe.filter((t) => t.status === "Done");
        default:
          return forMe.filter((t) => t.status !== "Done");
      }
    }, [forMe, scope, todayStr]);
    const sorted = useMemo(() => filtered.slice().sort((a, b) => ((a.due_at || "") > (b.due_at || "") ? 1 : -1)), [filtered]);
    return (
      <>
        <div className="chipbar">
          <button className={`chip ${scope === "today" ? "active" : ""}`} onClick={() => setScope("today")}>Today</button>
          <button className={`chip ${scope === "upcoming" ? "active" : ""}`} onClick={() => setScope("upcoming")}>Upcoming</button>
          <button className={`chip ${scope === "done" ? "active" : ""}`} onClick={() => setScope("done")}>Done</button>
          <button className={`chip ${scope === "all" ? "active" : ""}`} onClick={() => setScope("all")}>All</button>
        </div>
        <div className="board">
          <Column
            title={scope === "today" ? "Today" : scope === "upcoming" ? "Upcoming" : scope === "done" ? "Done" : "My tasks"}
            filter={() => true}
            tasks={sorted}
            reload={reload}
            compact={compact}
            meId={meId}
            isAdmin={false}
          />
        </div>
      </>
    );
  }

  // ADMIN VIEW
  const [view, setView] = useState("overview"); // overview | perUser
  const [statusFilter, setStatusFilter] = useState("all"); // all | active | new | rejected | done
  const [userFilter, setUserFilter] = useState("");

  const statusMatch = (t) => {
    switch (statusFilter) {
      case "active": return t.status !== "Done" && t.status !== "Rejected";
      case "new": return t.status === "New";
      case "rejected": return t.status === "Rejected";
      case "done": return t.status === "Done";
      default: return true;
    }
  };

  const usersFromTasks = useMemo(() => {
    const map = new Map();
    for (const t of tasksTextFiltered) if (t.assignee_user_id != null) map.set(t.assignee_user_id, `User ${t.assignee_user_id}`);
    for (const u of USERS) if (map.has(u.id)) map.set(u.id, u.name);
    return Array.from(map.entries()).sort((a, b) => String(a[1]).localeCompare(String(b[1])));
  }, [tasksTextFiltered]);

  const sorted = useMemo(
    () => tasksTextFiltered.slice().sort((a, b) => ((a.due_at || "") > (b.due_at || "") ? 1 : -1)),
    [tasksTextFiltered]
  );
  const filtered = useMemo(() => sorted.filter(statusMatch), [sorted, statusFilter]);

  const col = (title, filter) => (
    <Column title={title} filter={filter} tasks={filtered} reload={reload} compact={compact} meId={meId} isAdmin={true} />
  );

  return (
    <>
      <div className="filterbar">
        <label className="inline no-shrink">
          View
          <select className="select-sm" value={view} onChange={(e) => setView(e.target.value)}>
            <option value="overview">Overview</option>
            <option value="perUser">Per user</option>
          </select>
        </label>

        <label className="inline no-shrink">
          Status
          <select className="select-sm" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="new">New</option>
            <option value="rejected">Rejected</option>
            <option value="done">Done</option>
          </select>
        </label>

        {view === "perUser" && (
          <label className="inline no-shrink">
            User
            <select className="select-sm" value={userFilter} onChange={(e) => setUserFilter(e.target.value)}>
              <option value="">(select user)</option>
              {usersFromTasks.map(([id, name]) => (
                <option key={id} value={String(id)}>{name}</option>
              ))}
            </select>
          </label>
        )}
      </div>

      {view === "overview" ? (
        statusFilter === "all" ? (
          <div className="board">
            {col("New", (t) => t.status === "New")}
            {col("Rejected", (t) => t.status === "Rejected")}
            {col("Done", (t) => t.status === "Done")}
          </div>
        ) : (
          <div className="board">
            {col(statusFilter === "active" ? "Active" : statusFilter.charAt(0).toUpperCase() + statusFilter.slice(1), () => true)}
          </div>
        )
      ) : (
        <div className="board">
          {userFilter ? (
            <>
              {col(
                "Active",
                (t) =>
                  String(t.assignee_user_id) === String(userFilter) &&
                  (statusFilter === "all" ? t.status !== "Done" && t.status !== "Rejected" : statusMatch(t))
              )}
              {(statusFilter === "all" || statusFilter === "done") &&
                col("Done", (t) => String(t.assignee_user_id) === String(userFilter) && t.status === "Done")}
              {statusFilter === "rejected" &&
                col("Rejected", (t) => String(t.assignee_user_id) === String(userFilter) && t.status === "Rejected")}
            </>
          ) : (
            <div className="card empty" style={{ margin: "8px 10px" }}>
              Choose a user to view their tasks.
            </div>
          )}
        </div>
      )}
    </>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: ROUTE_TAB
   Purpose: Show today's route list and open Google route
   ================================================================= */
function RouteTab({ tasksForMeToday }) {
  const sorted = tasksForMeToday.slice().sort((a, b) => new Date(a.due_at) - new Date(b.due_at));
  const openSmartRoute = () => {
    const addrs = sorted.map((t) => t.address).filter(Boolean);
    const url = buildSmartRouteUrl(addrs);
    if (url) window.open(url, "_blank");
  };
  return (
    <div style={{ padding: "8px 12px" }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ opacity: 0.85 }}>{sorted.length} visits today</div>
        <button className="btn btn-primary" onClick={openSmartRoute}>
          Open Smart Route
        </button>
      </div>
      {sorted.map((t) => (
        <div key={t.id} className="task">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div className="title">{t.title}</div>
            <small className="badge">{t.status}</small>
          </div>
          <div className="meta">
            {fmtNO(t.due_at)} • Address: {t.address || "-"}
          </div>
          <div className="btns">
            <button
              className="btn"
              onClick={() =>
                window.open(
                  `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(t.address || "London")}`,
                  "_blank"
                )
              }
            >
              Open in Maps
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: BOTTOM_NAV
   Purpose: Sticky bottom navigation
   ================================================================= */
function BottomNav({ onBack, onHome, onOverview }) {
  return (
    <nav className="bottom-nav" role="navigation" aria-label="Primary">
      <button className="bnav-btn" onClick={onBack}>
        <div className="bnav-ico">🔙</div>
        <div className="bnav-txt">Back</div>
      </button>
      <button className="bnav-btn" onClick={onHome}>
        <div className="bnav-ico">🏠</div>
        <div className="bnav-txt">Home</div>
      </button>
      <button className="bnav-btn" onClick={onOverview}>
        <div className="bnav-ico">⬜</div>
        <div className="bnav-txt">Overview</div>
      </button>
    </nav>
  );
}
/* =========================== END BLOCK =========================== */


/* ================================================================
   BLOCK: APP
   Purpose: App shell; role, tabs, global search and modals
   ================================================================= */
function App() {
  const [compact] = useState(true);
  const [activeTab, setActiveTab] = useState("board");
  const [authed, setAuthed] = useState(!!localStorage.getItem("user"));
  const [showCreate, setShowCreate] = useState(false);
  const { tasks, reload } = useTasks();

  const path = window.location.pathname;
  useEffect(() => {
    if (!authed && path !== "/login") window.location.replace("/login");
    if (authed && path === "/login") window.location.replace("/");
  }, [authed, path]);

  const onDemoLogin = (u) => {
    localStorage.setItem("user", u);
    setAuthed(true);
    window.location.replace("/");
  };
  const onGoogleLogin = () => alert("Google Sign-In placeholder.");
  if (!authed) return <Login onDemoLogin={onDemoLogin} onGoogleLogin={onGoogleLogin} />;

  const role = localStorage.getItem("user") || "paddy";
  const meId = role === "ulf" ? 2 : role === "una" ? 3 : 1;
  const isAdmin = role === "paddy";

  // Mark body for role-specific UI (e.g., admin swipe hint -> Delete)
  useEffect(() => {
    document.body.classList.toggle("is-admin", isAdmin);
  }, [isAdmin]);

  const todayISO = new Date().toISOString().slice(0, 10);
  const myAssigned = (tasks || []).filter((t) => t.assignee_user_id === meId && t.status !== "Done" && t.due_at);
  const tasksForMeToday = myAssigned.filter((t) => onlyDateStr(t.due_at) === todayISO);

  const openSmartRoute = () => {
    if (!tasksForMeToday.length) return;
    const addrs = tasksForMeToday.map((t) => t.address).filter(Boolean);
    const url = buildSmartRouteUrl(addrs);
    if (url) window.open(url, "_blank");
  };

  const [editTask, setEditTask] = useState(null);
  useEffect(() => {
    const handler = (e) => setEditTask(e.detail.task);
    window.addEventListener("edit-task", handler);
    return () => window.removeEventListener("edit-task", handler);
  }, []);

  const [historyStudentId, setHistoryStudentId] = useState(null);
  useEffect(() => {
    const h = (e) => setHistoryStudentId(e.detail.studentId);
    document.addEventListener("open-history", h);
    return () => document.removeEventListener("open-history", h);
  }, []);

  const goBack = () => {
    if (window.history.length > 1) window.history.back();
    else window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const goHome = () => {
    setActiveTab("board");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const goOverview = () => {
    document.dispatchEvent(new CustomEvent("open-drawer"));
  };

  // Global search query
  const [q, setQ] = useState("");

  return (
    <>
      <Header
        onOpenSmartRoute={openSmartRoute}
        todaysCount={tasksForMeToday.length}
        onCreate={() => setShowCreate(true)}
        isAdmin={isAdmin}
      />

      {/* Compact search row (below header) */}
      <div style={{ background: "#fff", borderBottom: "1px solid var(--border)", padding: "8px 12px" }}>
        <SearchBar value={q} onChange={setQ} />
      </div>

      {/* Tabs row: Board + (admin-only) New Task button on the right */}
      <div className="tabs">
        <div className="tabs-left">
          <button className={activeTab === "board" ? "tab active" : "tab"} onClick={() => setActiveTab("board")}>
            Board
          </button>
          {!isAdmin && (
            <button className={activeTab === "route" ? "tab active" : "tab"} onClick={() => setActiveTab("route")}>
              Route
            </button>
          )}
        </div>

        <div className="tabs-right">
          {isAdmin && (
            <button className="tab link no-shrink" onClick={() => setShowCreate(true)} aria-label="Create new task">
              New task
            </button>
          )}
        </div>
      </div>

      {activeTab === "board" ? (
        <AdminBoard compact={compact} tasks={tasks} reload={reload} isAdmin={isAdmin} meId={meId} query={q} />
      ) : (
        <RouteTab tasksForMeToday={tasksForMeToday} />
      )}

      {isAdmin && showCreate && (
        <CreateModal defaultAssigneeId={2} onClose={() => setShowCreate(false)} onCreated={reload} />
      )}

      {editTask && <EditModal task={editTask} onClose={() => setEditTask(null)} onSaved={reload} isAdmin={isAdmin} />}

      {historyStudentId && <HistoryModal studentId={historyStudentId} onClose={() => setHistoryStudentId(null)} />}

      <BottomNav onBack={goBack} onHome={goHome} onOverview={goOverview} />
    </>
  );
}
/* =========================== END BLOCK =========================== */

createRoot(document.getElementById("root")).render(<App />);
