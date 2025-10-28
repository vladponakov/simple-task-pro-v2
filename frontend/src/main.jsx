import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

/* ---------------- Feature flags ---------------- */
const FLAGS = { dnd: true, bulk: true, filters: true, modernTheme: true };

/* ---------------- API helper ---------------- */
const API = (path, opts = {}) =>
  fetch(`http://localhost:8000${path}`, {
    headers: {
      "X-User": localStorage.getItem("user") || "paddy",
      "Content-Type": "application/json",
    },
    ...opts,
  }).then(async (r) => {
    if (!r.ok) throw new Error((await r.text()) || r.statusText);
    return r.json();
  });

/* ---------------- Helpers ---------------- */
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

const dNO = (iso) =>
  iso
    ? new Date(iso).toLocaleDateString("no-NO", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
    : "-";

const toIso = (v) => {
  if (!v) return null;
  const d = typeof v === "string" ? new Date(v) : v;
  return isNaN(d) ? null : d.toISOString();
};

const todayAt = (hh = 10, mm = 0) => {
  const d = new Date();
  d.setHours(hh, mm, 0, 0);
  return d.toISOString();
};

function buildSmartRouteUrl(addresses) {
  if (!addresses || addresses.length === 0) return null;
  const enc = (s) => encodeURIComponent(s || "London");
  if (addresses.length === 1) {
    return `https://www.google.com/maps/dir/?api=1&destination=${enc(
      addresses[0]
    )}`;
  }
  const dest = enc(addresses[addresses.length - 1]);
  const waypoints = addresses.slice(0, -1).map(enc).join("|");
  return `https://www.google.com/maps/dir/?api=1&travelmode=driving&destination=${dest}&waypoints=${waypoints}`;
}

const minutes = (n) => Math.round(n);
function estimateDurations(stops) {
  const perStop = 15;
  const perHop = 12;
  const total = stops.length * perStop + Math.max(0, stops.length - 1) * perHop;
  return { totalMinutes: total, perStop, perHop };
}

const USERS = [
  { id: 1, name: "Paddy MacGrath (Admin)" },
  { id: 2, name: "Ulf (User 1)" },
  { id: 3, name: "Una (User 2)" },
  { id: 4, name: "Liam (User 3)" },
];

/* ---------------- Auth / Login ---------------- */
function Login({ onDemoLogin, onGoogleLogin }) {
  const USERS_LOGIN = [
    { id: "paddy", label: "Admin (paddy)" },
    { id: "ulf", label: "User 1 (Ulf)" },
    { id: "una", label: "User 2 (Una)" },
    { id: "liam", label: "User 3 (Liam)" },
  ];
  const DEMO_PW = { paddy: "admin123", ulf: "user1", una: "user2", liam: "user3" };

  const [who, setWho] = useState("paddy");
  const [pw, setPw] = useState("");

  const login = () => {
    if ((DEMO_PW[who] || "") !== pw.trim()) {
      alert("Wrong password. Demo → paddy:admin123, ulf:user1, una:user2, liam:user3");
      return;
    }
    onDemoLogin(who);
    window.location.replace("/");
  };

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="brand">Simple Task Pro</div>
        <div className="sub">Sign in to continue</div>

        <div className="field">
          <label className="label">User</label>
          <select
            className="select"
            value={who}
            onChange={(e) => setWho(e.target.value)}
          >
            {USERS_LOGIN.map((u) => (
              <option key={u.id} value={u.id}>
                {u.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="label">Password</label>
          <input
            type="password"
            className="input"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            placeholder="••••••••"
          />
        </div>

        <button className="btn btn-primary" onClick={login}>
          Sign in
        </button>

        <div className="divider">or</div>
        <button className="oauth-btn" onClick={onGoogleLogin}>
          Continue with Google
        </button>

        <div className="sub" style={{ marginTop: 10, fontSize: 12 }}>
          Demo creds → paddy:admin123, ulf:user1, una:user2, liam:user3
        </div>
      </div>
    </div>
  );
}

/* ---------------- Header ---------------- */
function Header({ compact, setCompact, onOpenSmartRoute, todaysCount, onCreate }) {
  const [me, setMe] = useState(null);
  useEffect(() => {
    API("/api/me").then(setMe).catch(() => {});
  }, []);
  const role = localStorage.getItem("user") || "paddy";
  const isAdmin = role === "paddy";

  return (
    <div className="app-header">
      <div className="app-title">Simple Task Pro</div>
      <div className="spacer" />
      {isAdmin && (
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ opacity: 0.8 }}>Act as:</span>
          <select
            className="select"
            value={role}
            onChange={(e) => {
              localStorage.setItem("user", e.target.value);
              location.reload();
            }}
          >
            <option value="paddy">Paddy MacGrath (Admin)</option>
            <option value="ulf">Ulf (User 1)</option>
            <option value="una">Una (User 2)</option>
            <option value="liam">Liam (User 3)</option>
          </select>
        </label>
      )}
      <div style={{ opacity: 0.8, marginLeft: 10 }}>
        {me ? `${me.name} • ${me.role}` : ""}
      </div>
      <button
        className="btn"
        style={{ marginLeft: 12 }}
        onClick={() => {
          localStorage.removeItem("user");
          window.location.replace("/login");
        }}
      >
        Logout
      </button>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: 12 }}>
        <button className="btn" onClick={() => setCompact(!compact)}>
          {compact ? "Compact: ON" : "Compact: OFF"}
        </button>
        {isAdmin && (
          <button className="btn" onClick={onCreate}>
            + New Task
          </button>
        )}
        <button className="btn btn-primary" onClick={onOpenSmartRoute}>
          Smart Route (today){todaysCount ? ` • ${todaysCount}` : ""}
        </button>
      </div>
    </div>
  );
}

/* ---------------- Comments ---------------- */
function TaskComments({ taskId }) {
  const [comments, setComments] = useState([]);
  const [text, setText] = useState("");

  const load = () =>
    API(`/api/tasks/${taskId}/comments`)
      .then(setComments)
      .catch(() => setComments([]));

  useEffect(load, [taskId]);

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
            <span style={{ opacity: 0.8 }}>{c.author || "User"}</span>
            {" • "}
            <span style={{ opacity: 0.7 }}>
              {new Date(c.created_at).toLocaleString("no-NO")}
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

/* ---------------- Modal (Create) ---------------- */
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
      setErr("Select student");
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
          body: null,
          due_at: todayAt(10, 0), // auto today 10:00
          assignee_user_id: defaultAssigneeId, // default → Ulf
          status: "Assigned",
          reason: reason || null,
          checklist: [],
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
        <textarea className="input" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />

        <div className="meta" style={{ marginTop: 8, opacity: 0.8 }}>
          Due: today 10:00 (set automatically)
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

/* ---------------- Modal (Edit) ---------------- */
function EditModal({ task, onClose, onSaved, isAdmin }) {
  const [title, setTitle] = useState(task.title);
  const [address, setAddress] = useState(task.address || "");
  const [dueAt, setDueAt] = useState(task.due_at || "");
  const [reason, setReason] = useState(task.reason || "");
  const [assignee, setAssignee] = useState(task.assignee_user_id || 2);

  const [checklist, setChecklist] = useState(
    Array.isArray(task.checklist) ? task.checklist : []
  );
  const [newItem, setNewItem] = useState("");

  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // close on ESC, freeze background scroll
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
    reason: reason || null,
    checklist,
  };

  const save = async () => {
    setSaving(true);
    setErr("");
    try {
      await API(`/api/tasks/${task.id}`, {
        method: "PUT",
        body: JSON.stringify(payloadBase),
      });
      await onSaved();
      onClose(); // ✅ close after save
    } catch (e) {
      setErr(e?.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const saveAndAssignToday = async () => {
    if (!isAdmin) return save(); // safety for non-admins
    setSaving(true);
    setErr("");
    try {
      await API(`/api/tasks/${task.id}`, {
        method: "PUT",
        body: JSON.stringify({
          ...payloadBase,
          due_at: todayAt(10, 0),
          status: "Assigned",
        }),
      });
      await API(`/api/tasks/${task.id}/assign`, {
        method: "POST",
        body: JSON.stringify({ assignee_user_id: Number(assignee) }),
      });
      await onSaved();
      onClose(); // ✅ close after save & assign
    } catch (e) {
      setErr(e?.message || "Failed to save & assign");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        onClick={(e) => e.stopPropagation()} // don't close when clicking inside
      >
        {/* Header with explicit Close (×) */}
        <div className="row" style={{ alignItems: "center", marginBottom: 8 }}>
          <h3 style={{ margin: 0, flex: 1 }}>Edit task</h3>
          <button
            className="btn"
            onClick={onClose}
            aria-label="Close"
            title="Close"
            style={{
              padding: "6px 10px",
              lineHeight: 1,
              fontWeight: 700,
              borderRadius: 8,
            }}
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
        <textarea className="input" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />

        {/* Checklist */}
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
                <button className="btn btn-danger" onClick={() => removeItem(i)}>Remove</button>
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
            <button className="btn" onClick={addItem}>Add</button>
          </div>
        </div>

        {/* Assign (Admin only) */}
        {isAdmin && (
          <div className="row" style={{ gap: 8, marginTop: 10 }}>
            <label className="label" style={{ margin: 0 }}>Assign to</label>
            <select
              className="select"
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
            >
              {USERS.filter(u => u.id !== 1).map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          </div>
        )}

        <div className="btns" style={{ marginTop: 12, gap: 8, flexWrap: "wrap" }}>
          <button className="btn" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn" onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </button>
          {isAdmin && (
            <button className="btn btn-primary" onClick={saveAndAssignToday} disabled={saving}>
              {saving ? "Working..." : "Save & Assign (today)"}
            </button>
          )}
        </div>

        <TaskComments taskId={task.id} />
      </div>
    </div>
  );
}


/* ---------------- Hooks ---------------- */
function useTasks() {
  const [tasks, setTasks] = useState([]);
  const reload = () => API("/api/tasks").then(setTasks).catch(() => setTasks([]));
  useEffect(() => {
    reload();
  }, []);
  return { tasks, reload };
}

/* ---------------- Filter bar ---------------- */
function FilterBar({ setQuery, setStatus, setUser, bulkMode, setBulkMode }) {
  if (!FLAGS.filters && !FLAGS.bulk) return null;
  return (
    <div className="filterbar">
      {FLAGS.filters && (
        <>
          <input
            className="input"
            placeholder="Search student/title/address..."
            onChange={(e) => setQuery(e.target.value.toLowerCase())}
          />
          <select
            className="select-sm"
            onChange={(e) => setStatus(e.target.value)}
            defaultValue=""
          >
            <option value="">All statuses</option>
            <option>New</option>
            <option>Assigned</option>
            <option>Accepted</option>
            <option>Rejected</option>
            <option>Done</option>
          </select>
          <select
            className="select-sm"
            onChange={(e) => setUser(e.target.value)}
            defaultValue=""
          >
            <option value="">All users</option>
            <option value="2">User 1 (Ulf)</option>
            <option value="3">User 2 (Una)</option>
            <option value="4">User 3 (Liam)</option>
            <option value="none">Unassigned</option>
          </select>
        </>
      )}
      {FLAGS.bulk && (
        <button className="btn" onClick={() => setBulkMode(!bulkMode)}>
          {bulkMode ? "Exit Bulk" : "Bulk select"}
        </button>
      )}
    </div>
  );
}

/* ---------------- Task / Column / Bulk ---------------- */
function TaskCard({ t, reload, bulkMode, toggleSelect, selected, compact, meId, isAdmin }) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState([]);
  const [showEdit, setShowEdit] = useState(false);

  const loadHistory = () =>
    API(`/api/students/${t.student_id}/history?days=90`).then(setHistory);

  const act = (action, reason) =>
    API(`/api/tasks/${t.id}/status`, {
      method: "POST",
      body: JSON.stringify({ action, reason }),
    }).then(reload);

  const onDragStart = (e) => {
    if (!FLAGS.dnd) return;
    e.dataTransfer.setData("text/taskId", String(t.id));
  };

  const canEdit = isAdmin || t.assignee_user_id === meId;

  return (
    <div
      className={`task ${compact ? "compact" : ""}`}
      draggable={FLAGS.dnd}
      onDragStart={onDragStart}
    >
      <div className="row">
        <div className="title">{t.title}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {bulkMode && (
            <input
              type="checkbox"
              className="checkbox"
              checked={!!selected}
              onChange={() => toggleSelect(t.id)}
            />
          )}
          <small className="badge">{t.status}</small>
        </div>
      </div>
      <div className="meta">
        Due: {fmtNO(t.due_at)} • Address: {t.address || "-"}
      </div>
      {t.reason && (
        <div className="meta" style={{ marginTop: 4, opacity: 0.85 }}>
          Reason: {t.reason}
        </div>
      )}
      <div className="btns">
        <button
          className="btn"
          onClick={() => {
            setHistoryOpen(true);
            loadHistory();
          }}
        >
          History
        </button>

        {canEdit && (
          <button className="btn" onClick={() => setShowEdit(true)}>
            Edit
          </button>
        )}

        <button
          className="btn"
          onClick={() =>
            window.open(
              `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                t.address || "London"
              )}`,
              "_blank"
            )
          }
        >
          Open in Maps
        </button>
        <button className="btn" onClick={() => act("accept")}>
          Accept
        </button>
        <button
          className="btn"
          onClick={() => {
            const r = prompt("Reject reason?");
            if (r) act("reject", r);
          }}
        >
          Reject
        </button>
        <button className="btn btn-primary" onClick={() => act("complete")}>
          Complete
        </button>
      </div>

      {showEdit && (
        <EditModal
          task={t}
          onClose={() => setShowEdit(false)}
          onSaved={reload}
          isAdmin={isAdmin}
        />
      )}

      {historyOpen && (
        <div
          style={{
            marginTop: 8,
            padding: 10,
            background: "rgba(2,6,23,.5)",
            border: "1px solid var(--border)",
            borderRadius: 12,
          }}
        >
          <div className="row">
            <strong>Student history (last 90 days)</strong>
            <button className="btn" onClick={() => setHistoryOpen(false)}>
              Close
            </button>
          </div>
          <ul>
            {history.map((h, i) => (
              <li key={i} style={{ color: "var(--muted)" }}>
                {h.kind === "absence"
                  ? `[Absence] ${dNO(h.date)} • ${h.reason_code} • ${h.reported_by} • ${h.note || ""}`
                  : `[Visit] ${dNO(h.date)} • ${h.title}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Column({
  title,
  filter,
  dropAction,
  tasks,
  reload,
  bulkMode,
  selection,
  toggleSelect,
  compact,
  meId,
  isAdmin,
}) {
  const [dropping, setDropping] = useState(false);
  const list = tasks.filter(filter);
  const onDragOver = (e) => {
    if (FLAGS.dnd) {
      e.preventDefault();
      setDropping(true);
    }
  };
  const onDragLeave = () => setDropping(false);
  const onDrop = async (e) => {
    if (!FLAGS.dnd) return;
    e.preventDefault();
    setDropping(false);
    const id = Number(e.dataTransfer.getData("text/taskId"));
    if (!id) return;
    await dropAction?.(id);
    reload();
  };
  return (
    <div
      className={dropping ? "col dropping" : "col"}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <h3>{title}</h3>
      <div className="drop-hint">Drop here</div>
      {list.map((t) => (
        <TaskCard
          key={t.id}
          t={t}
          reload={reload}
          bulkMode={bulkMode}
          selected={selection.has(t.id)}
          toggleSelect={toggleSelect}
          compact={compact}
          meId={meId}
          isAdmin={isAdmin}
        />
      ))}
    </div>
  );
}

function BulkBar({ selection, reload }) {
  const ids = Array.from(selection);
  if (ids.length === 0) return null;

  const bulkAssign = async (assignee_user_id) => {
    await Promise.all(
      ids.map((id) =>
        API(`/api/tasks/${id}/assign`, {
          method: "POST",
          body: JSON.stringify({ assignee_user_id }),
        })
      )
    );
    reload();
  };
  const bulkComplete = async () => {
    await Promise.all(
      ids.map((id) =>
        API(`/api/tasks/${id}/status`, {
          method: "POST",
          body: JSON.stringify({ action: "complete" }),
        })
      )
    );
    reload();
  };
  const bulkDelete = async () => {
    if (!confirm("Delete selected tasks?")) return;
    await Promise.all(
      ids.map((id) =>
        fetch(`http://localhost:8000/api/tasks/${id}`, {
          method: "DELETE",
          headers: { "X-User": localStorage.getItem("user") || "paddy" },
        })
      )
    );
    reload();
  };

  return (
    <div className="bulkbar">
      <div style={{ opacity: 0.8 }}>Selected: {ids.length}</div>
      <button className="btn" onClick={() => bulkAssign(2)}>
        Assign to Ulf
      </button>
      <button className="btn" onClick={() => bulkAssign(3)}>
        Assign to Una
      </button>
      <button className="btn" onClick={() => bulkAssign(4)}>
        Assign to Liam
      </button>
      <button className="btn btn-primary" onClick={bulkComplete}>
        Mark Complete
      </button>
      <button className="btn btn-danger" onClick={bulkDelete}>
        Delete
      </button>
    </div>
  );
}

/* ---------------- Admin Board ---------------- */
function AdminBoard({ compact, tasks, reload, isAdmin, meId, onCreate }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [user, setUser] = useState("");
  const [bulkMode, setBulkMode] = useState(false);
  const [selection, setSelection] = useState(new Set());

  const toggleSelect = (id) => {
    const s = new Set(selection);
    s.has(id) ? s.delete(id) : s.add(id);
    setSelection(s);
  };

  const filtered = useMemo(() => {
    return tasks.filter((t) => {
      if (query && !`${t.title}|${t.address || ""}`.toLowerCase().includes(query))
        return false;
      if (status && t.status !== status) return false;
      if (user) {
        if (user === "none" && t.assignee_user_id != null) return false;
        if (user !== "none" && String(t.assignee_user_id) !== String(user))
          return false;
      }
      return true;
    });
  }, [tasks, query, status, user]);

  const assignTo = (uid) => async (taskId) =>
    API(`/api/tasks/${taskId}/assign`, {
      method: "POST",
      body: JSON.stringify({ assignee_user_id: uid }),
    });

  const markDone = async (taskId) =>
    API(`/api/tasks/${taskId}/status`, {
      method: "POST",
      body: JSON.stringify({ action: "complete" }),
    });

  const col = (title, filter, dropAction) => (
    <Column
      title={title}
      filter={filter}
      tasks={filtered}
      reload={reload}
      bulkMode={bulkMode}
      selection={selection}
      toggleSelect={toggleSelect}
      dropAction={dropAction}
      compact={compact}
      meId={meId}
      isAdmin={isAdmin}
    />
  );

  return (
    <>
      <FilterBar
        setQuery={setQuery}
        setStatus={setStatus}
        setUser={setUser}
        bulkMode={bulkMode}
        setBulkMode={setBulkMode}
      />

      {/* New Task button - Admin only */}
      {isAdmin && (
        <div className="row" style={{ padding: "0 8px 8px", gap: 8 }}>
          <button className="btn btn-primary" onClick={onCreate}>
            + New Task
          </button>
        </div>
      )}

      <div className="board">
        {isAdmin ? (
          <>
            {col("New", (t) => t.status === "New", null)}
            {col("User 1", (t) => t.assignee_user_id === 2 && t.status !== "Done", assignTo(2))}
            {col("User 2", (t) => t.assignee_user_id === 3 && t.status !== "Done", assignTo(3))}
            {col("User 3", (t) => t.assignee_user_id === 4 && t.status !== "Done", assignTo(4))}
            {col("Done", (t) => t.status === "Done", markDone)}
          </>
        ) : (
          <>
            {col("My tasks", (t) => t.assignee_user_id === meId && t.status !== "Done", null)}
            {col("Done", (t) => t.assignee_user_id === meId && t.status === "Done", null)}
          </>
        )}
      </div>

      <BulkBar selection={selection} reload={reload} />
    </>
  );
}

/* ---------------- Route Tab ---------------- */
function RouteTab({ tasksForMeToday }) {
  const sorted = tasksForMeToday
    .slice()
    .sort((a, b) => new Date(a.due_at) - new Date(b.due_at));
  const est = estimateDurations(sorted);
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
      <div style={{ opacity: 0.8, marginBottom: 10 }}>
        Estimate ~ {minutes(est.totalMinutes)} min (incl. travel).
      </div>
      {sorted.map((t) => (
        <div key={t.id} className="task">
          <div className="row">
            <div className="title">{t.title}</div>
            <small className="badge">{t.status}</small>
          </div>
          <div className="meta">
            Due: {fmtNO(t.due_at)} • Address: {t.address || "-"}
          </div>
          <div className="btns">
            <button
              className="btn"
              onClick={() =>
                window.open(
                  `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                    t.address || "London"
                  )}`,
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

/* ---------------- App ---------------- */
function App() {
  const [compact, setCompact] = useState(false);
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
  const onGoogleLogin = () =>
    alert("Google Sign-In placeholder: configure OAuth backend.");

  if (!authed) return <Login onDemoLogin={onDemoLogin} onGoogleLogin={onGoogleLogin} />;

  const role = localStorage.getItem("user") || "paddy";
  const meId = role === "ulf" ? 2 : role === "una" ? 3 : role === "liam" ? 4 : 1;
  const isAdmin = role === "paddy";

  const todayISO = new Date().toISOString().slice(0, 10);
  const myAssigned = (tasks || []).filter(
    (t) => t.assignee_user_id === meId && t.status !== "Done" && t.due_at
  );
  const targetDate =
    myAssigned.find((t) => onlyDateStr(t.due_at) === todayISO)?.due_at ||
    todayISO;
  const tasksForMeToday = myAssigned.filter(
    (t) => onlyDateStr(t.due_at) === onlyDateStr(targetDate)
  );
  const todaysCount = tasksForMeToday.length;

  const openSmartRoute = () => {
    if (!tasksForMeToday.length) return;
    const addrs = tasksForMeToday.map((t) => t.address).filter(Boolean);
    const url = buildSmartRouteUrl(addrs);
    if (url) window.open(url, "_blank");
  };

  return (
    <>
      <Header
        compact={compact}
        setCompact={setCompact}
        onOpenSmartRoute={openSmartRoute}
        todaysCount={todaysCount}
        onCreate={() => setShowCreate(true)}
      />
      <div className="tabs">
        <button
          className={activeTab === "board" ? "tab active" : "tab"}
          onClick={() => setActiveTab("board")}
        >
          Board
        </button>
        <button
          className={activeTab === "route" ? "tab active" : "tab"}
          onClick={() => setActiveTab("route")}
        >
          Route
        </button>
      </div>
      {activeTab === "board" ? (
        <AdminBoard
          compact={compact}
          tasks={tasks}
          reload={reload}
          isAdmin={isAdmin}
          meId={meId}
          onCreate={() => setShowCreate(true)}
        />
      ) : (
        <RouteTab tasksForMeToday={tasksForMeToday} />
      )}

      {/* Admin-only create modal */}
      {isAdmin && showCreate && (
        <CreateModal
          defaultAssigneeId={2}
          onClose={() => setShowCreate(false)}
          onCreated={reload}
        />
      )}
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
