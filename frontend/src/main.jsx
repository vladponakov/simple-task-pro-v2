import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

/* ---------------- Feature flags ---------------- */
const FLAGS = { dnd: true, bulk: true, filters: true, modernTheme: true };

/* ---------------- API helper ---------------- */
const API = (path, opts = {}) =>
  fetch(`http://localhost:8000${path}`, {
    headers: {
      "X-User": localStorage.getItem("user") || "anna",
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
  const perStop = 15,
    perHop = 12;
  const total = stops.length * perStop + Math.max(0, stops.length - 1) * perHop;
  return { totalMinutes: total, perStop, perHop };
}

/* ---------------- Auth / Login ---------------- */
function Login({ onDemoLogin, onGoogleLogin }) {
  const USERS = [
    { id: "anna", label: "Admin (Anna)" },
    { id: "ulf", label: "User 1 (Ulf)" },
    { id: "una", label: "User 2 (Una)" },
    { id: "liam", label: "User 3 (Liam)" },
  ];
  const DEMO_PW = { anna: "admin123", ulf: "user1", una: "user2", liam: "user3" };

  const [who, setWho] = useState("anna");
  const [pw, setPw] = useState("");

  const login = () => {
    if ((DEMO_PW[who] || "") !== pw.trim()) {
      alert("Wrong password. Demo → anna:admin123, ulf:user1, una:user2, liam:user3");
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
            {USERS.map((u) => (
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
          Demo creds → anna:admin123, ulf:user1, una:user2, liam:user3
        </div>
      </div>
    </div>
  );
}

/* ---------------- Header ---------------- */
function Header({ compact, setCompact, onOpenSmartRoute, todaysCount }) {
  const [me, setMe] = useState(null);
  useEffect(() => {
    API("/api/me").then(setMe).catch(() => {});
  }, []);
  const role = localStorage.getItem("user") || "anna";
  const isAdmin = role === "anna";

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
            <option value="anna">Anna (Admin)</option>
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
        <button className="btn btn-primary" onClick={onOpenSmartRoute}>
          Smart Route (today){todaysCount ? ` • ${todaysCount}` : ""}
        </button>
      </div>
    </div>
  );
}

/* ---------------- Hooks ---------------- */
function useTasks() {
  const [tasks, setTasks] = useState([]);
  const reload = () => API("/api/tasks").then(setTasks).catch(() => setTasks([]));
  useEffect(reload, []);
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
function TaskCard({ t, reload, bulkMode, toggleSelect, selected, compact }) {
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

  const isAdmin = (localStorage.getItem("user") || "anna") === "anna";

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
        Due: {t.due_at || "-"} • Address: {t.address || "-"}
      </div>
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
        {isAdmin && (
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
      {isAdmin && showEdit && (
        <EditModal task={t} onClose={() => setShowEdit(false)} onSaved={reload} />
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
                  ? `[Absence] ${h.date} • ${h.reason_code} • ${h.reported_by} • ${h.note || ""}`
                  : `[Visit] ${h.date} • ${h.title}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Column({ title, filter, dropAction, tasks, reload, bulkMode, selection, toggleSelect, compact }) {
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
          headers: { "X-User": localStorage.getItem("user") || "anna" },
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
function AdminBoard({ compact, tasks, reload, isAdmin, meId }) {
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
            Due: {t.due_at || "-"} • Address: {t.address || "-"}
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

  const role = localStorage.getItem("user") || "anna";
  const meId = role === "ulf" ? 2 : role === "una" ? 3 : role === "liam" ? 4 : 1;
  const isAdmin = role === "anna";

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
        <AdminBoard compact={compact} tasks={tasks} reload={reload} isAdmin={isAdmin} meId={meId} />
      ) : (
        <RouteTab tasksForMeToday={tasksForMeToday} />
      )}
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
