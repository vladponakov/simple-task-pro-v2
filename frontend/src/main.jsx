import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

/* ================================================================
   BLOCK: API_HELPERS
   ================================================================= */
const isProd =
  typeof window !== "undefined" && !window.location.origin.includes("localhost");
const API_BASE = isProd
  ? ""
  : import.meta.env?.VITE_API_BASE ?? "http://localhost:8000";

const API = (path, opts = {}) => {
  const p = path.startsWith("/api")
    ? path
    : `/api${path.startsWith("/") ? "" : "/"}${path}`;

  const authToken = localStorage.getItem("auth_token");
  const xUser = localStorage.getItem("x_user");

  return fetch(`${API_BASE}${p}`, {
    headers: {
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...(xUser ? { "X-User": xUser } : {}),
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
    cache: "no-store",
    ...opts,
  }).then(async (r) => {
    if (!r.ok) {
  let message = "Request failed";
  try {
    const ct = r.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      const j = await r.json();
      if (j?.detail) {
        message = j.detail;
      } else if (j?.message) {
        message = j.message;
      }
    } else {
      const t = await r.text();
      if (t) message = t;
    }
  } catch {
    // hvis vi ikke klarer å lese body, beholder vi default message
  }
  throw new Error(message);
}

    return r.json();
  });
};

// Make.com prep (not used yet, but ready)
export const API_EXT = {
  createTask: (data) =>
    API("/api/tasks", { method: "POST", body: JSON.stringify(data) }),
  getDoneTasks: (since) =>
    API(
      `/api/tasks?status=Done${
        since ? `&updated_after=${encodeURIComponent(since)}` : ""
      }`
    ),
};
/* =========================== END BLOCK =========================== */

/* ================================================================
   BLOCK: UTILITIES
   ================================================================= */
const onlyDateStr = (d) => {
  if (!d) return null;
  const dt = new Date(d);
  if (Number.isNaN(dt.getTime())) return null;
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const day = String(dt.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};


const fmtNO = (iso) =>
  iso
    ? new Date(iso).toLocaleDateString("no-NO", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
    : "-";

const toIso = (v) => {
  if (!v) return null;
  const s = typeof v === "string" ? v.replace(" ", "T") : v;
  const d = new Date(s);
  return isNaN(d) ? null : d.toISOString();
};

const defaultDueAt = () => {
  const d = new Date();

  // Sett f.eks. til "nå" lokalt – hvis du heller vil ha 10:00 hver dag, kan vi justere det
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");

  // 🔹 Viktig: INGEN "Z" på slutten → tolkes som "lokal" / naiv, ikke UTC
  return `${y}-${m}-${day}T${hh}:${mm}:${ss}`;
};

// stops = all student addresses
// startAddress = optional fixed origin ("My school", "Big Ben", etc)
// ✅ External Google Maps directions URL
// 🔹 FULL MAP – use device position ("Posisjonen din")
function buildSmartRouteUrl(stops) {
  const enc = (s) => encodeURIComponent(s || "");
  if (!Array.isArray(stops) || stops.length === 0) return null;

  const destination = enc(stops[stops.length - 1]);
  const waypoints = stops.slice(0, -1).map(enc).join("|");

  // 💡 no origin here on purpose → Google uses "Posisjonen din"
  let url = "https://www.google.com/maps/dir/?api=1&travelmode=driving";
  url += `&destination=${destination}`;
  if (waypoints) url += `&waypoints=${waypoints}`;
  return url;
}

// 🔹 EMBED map – needs explicit origin (startAddress or first stop)
function buildSmartRouteEmbedUrl(stops, startAddress) {
  const key = import.meta.env?.VITE_GOOGLE_MAPS_EMBED_KEY;
  if (!key) return null;
  if (!Array.isArray(stops) || stops.length === 0) return null;

  const enc = (s) => encodeURIComponent(s || "");

  const hasOrigin = !!(startAddress && startAddress.trim());
  const origin = hasOrigin
    ? enc(startAddress.trim())
    : enc(stops[0]); // fallback: first stop

  const destination = enc(stops[stops.length - 1]);

  // use middle stops as waypoints (avoid duplicating origin)
  const middleStops = hasOrigin ? stops : stops.slice(1);
  const waypoints = middleStops.slice(0, -1).map(enc).join("|");

  let url = `https://www.google.com/maps/embed/v1/directions?key=${key}&origin=${origin}&destination=${destination}&mode=driving`;
  if (waypoints) url += `&waypoints=${waypoints}`;
  return url;
}


const titleCase = (s) =>
  (s || "")
    .toString()
    .replace(/\w\S*/g, (t) => t[0].toUpperCase() + t.slice(1).toLowerCase())
    .trim();

const getReason = (t) =>
  (
    t?.body ?? // unified reason field
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
   ================================================================= */

function Login({ onLoggedIn }) {
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [loading, setLoading] = useState(false);

const login = async () => {
  if (!email || !pw) return;
  setLoading(true);
  try {
    const res = await fetch(`${API_BASE}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: pw }),
    });
    if (!res.ok) {
      throw new Error("Invalid email or password");
    }
    const data = await res.json();
    const { token, user } = data;

    localStorage.setItem("auth_token", token);
    localStorage.setItem("current_user", JSON.stringify(user));
    localStorage.setItem("x_user", user.email);

    // ✅ samme flow som Google OAuth
    window.location.replace("/");
  } catch (err) {
    alert((err && err.message) || "Login failed");
  } finally {
    setLoading(false);
  }
};




  const loginWithGoogle = () => {
    window.location.href = `${API_BASE}/api/auth/google/start`;
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !loading) {
      login();
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-title">IDENTIFICATION</div>
        </div>

  <button
  className="google-btn"
  type="button"
  onClick={loginWithGoogle}
  disabled={loading}
>
  <span className="google-icon-wrapper" aria-hidden="true">
    <svg className="google-icon" viewBox="0 0 24 24">
      {/* Enkel “G” med fire farger – ikke 100% logo, men Google-ish */}
      <path
        d="M12 3.5c2.1 0 3.7.8 4.9 1.9l-1.9 2a4.3 4.3 0 0 0-3-1.1c-2.4 0-4.3 1.8-4.3 4.2s1.9 4.2 4.3 4.2c2.2 0 3.6-1.4 3.9-3.2H12v-2.7h7.1c.1.4.2.9.2 1.5 0 4.2-2.8 7.2-7.3 7.2C7.6 18.9 4 15.4 4 11.5 4 7.6 7.6 4 12 4z"
        fill="#4285F4"
      />
      <path d="M5.1 7.5 7.3 9.2" fill="#EA4335" />
      <path d="M5 15.3 7.2 13.5" fill="#34A853" />
      <path d="M15.8 6.1 18 4.3" fill="#FBBC05" />
    </svg>
  </span>
  <span className="google-btn-text">Sign in with Google</span>
</button>



        <div className="auth-divider">
          <span>OR</span>
        </div>

        <div className="auth-field">
          <label className="auth-label">Login</label>
          <input
            className="auth-input"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={onKeyDown}
          />
        </div>

        <div className="auth-field">
          <label className="auth-label">Password</label>
          <input
            className="auth-input"
            type="password"
            placeholder="••••••••"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            onKeyDown={onKeyDown}
          />
        </div>

        <button
          className="auth-submit"
          type="button"
          onClick={login}
          disabled={loading || !email || !pw}
        >
          {loading ? "Logging in..." : "Log In"}
        </button>

        <div className="auth-footer">
          <span>Visit Task Pro</span>
        </div>
      </div>
    </div>
  );
}

/* =========================== END BLOCK =========================== */

/* ================================================================
   BLOCK: HEADER + DRAWER
   ================================================================= */
function Header({
  onOpenSmartRoute,
  todaysCount,
  onCreate,
  isAdmin,
  onOpenSettings,
}) {
  const [me, setMe] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

   useEffect(() => {
    API("/api/me")
      .then((data) => {
        if (data && (data.name || data.email)) {
          setMe(data);
        } else {
          const raw = localStorage.getItem("current_user");
          if (raw) {
            try {
              setMe(JSON.parse(raw));
            } catch {
              /* ignore */
            }
          }
        }
      })
      .catch(() => {
        const raw = localStorage.getItem("current_user");
        if (raw) {
          try {
            setMe(JSON.parse(raw));
          } catch {
            /* ignore */
          }
        }
      });
  }, []);


  useEffect(() => {
    const open = () => setDrawerOpen(true);
    document.addEventListener("open-drawer", open);
    return () => document.removeEventListener("open-drawer", open);
  }, []);

  const initials = (me?.name || me?.email || "User")
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
        <div className="app-title">Visit Task Pro</div>
        <div className="spacer" />
        <button
          className="btn btn-primary pill"
          style={{ marginLeft: 8 }}
          onClick={onOpenSmartRoute}
        >
          Smart Route
          {todaysCount ? ` • ${todaysCount}` : ""}
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
        <header className="drawer-header">
          <strong>Menu</strong>
          <button className="btn ghost" onClick={() => setDrawerOpen(false)}>
            ✕
          </button>
        </header>

        <div className="userbox">
          <div className="avatar">{initials}</div>
          <div className="meta">
            <div className="name">{me ? me.name : "—"}</div>
            <div className="rolepill">{me ? me.role : ""}</div>
          </div>
        </div>

        <div className="menu">
  <button
    className="mitem mitem--action"
    onClick={() => {
      setDrawerOpen(false);
      onCreate();
    }}
  >
    + New task
  </button>

  <button
  className="mitem"
  onClick={() => {
    setDrawerOpen(false);
    onOpenSettings();
  }}
>
  Settings
</button>



          <button
            className="mitem mitem--danger"
            onClick={() => {
              localStorage.removeItem("auth_token");
              localStorage.removeItem("current_user");
              localStorage.removeItem("x_user");
              window.location.replace("/login");
            }}
          >
            Logout
          </button>
        </div>
      </aside>
    </>
  );
}
/* =========================== END BLOCK =========================== */

/* ================================================================
   BLOCK: SETTINGS_MODAL
   ================================================================= */
function SettingsModal({ onClose }) {
  const [tab, setTab] = useState("batch"); // batch | students | users
  const [editUserId, setEditUserId] = useState("");
  const [editUserRole, setEditUserRole] = useState("USER");
  const [editUserStartAddress, setEditUserStartAddress] = useState("");
  const [students, setStudents] = useState([]);
  const [users, setUsers] = useState([]);

  const [studentName, setStudentName] = useState("");
  const [studentClass, setStudentClass] = useState("");
  const [studentAddress, setStudentAddress] = useState("");
  const [deleteStudentId, setDeleteStudentId] = useState("");

 const [userName, setUserName] = useState("");
const [userEmail, setUserEmail] = useState("");
const [userPassword, setUserPassword] = useState("");   // NEW
const [userRole, setUserRole] = useState("USER");
const [deleteUserId, setDeleteUserId] = useState("");

const [batchSettings, setBatchSettings] = useState(() => {
  try {
    const raw = localStorage.getItem("batchSettings");
    if (!raw) {
      return { rolloverAt: "17:00", timezone: "Europe/London" };
    }
    const parsed = JSON.parse(raw);
    return {
      rolloverAt: parsed.rolloverAt || "17:00",
      timezone: parsed.timezone || "Europe/London",
    };
  } catch {
    return { rolloverAt: "17:00", timezone: "Europe/London" };
  }
});

const TIMEZONES = [
  { value: "Europe/London", label: "London (UK / UTC)" },
  { value: "Europe/Oslo", label: "Oslo (Norway)" },
];



    const load = async () => {
    try {
      const [st, us, batch] = await Promise.all([
        API("/api/students"),
        API("/api/users"),
        API("/api/settings/batch"),
      ]);
      setStudents(st || []);
      setUsers(us || []);
      if (batch && typeof batch.rollover_hour === "number") {
        const hh = String(batch.rollover_hour).padStart(2, "0");
        setBatchSettings({
          rolloverAt: `${hh}:00`,
          timezone: batch.rollover_timezone || "Europe/London",
        });
      }
    } catch (e) {
      console.error("Failed to load settings data", e);
    }
  };



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

   useEffect(() => {
    load();
  }, []);

    useEffect(() => {
    if (!editUserId) {
      setEditUserRole("USER");
      setEditUserStartAddress("");
      return;
    }
    const u = users.find((x) => String(x.id) === String(editUserId));
    if (!u) return;

    const r = (u.role || "").toString().toUpperCase();
    setEditUserRole(r === "ADMIN" ? "ADMIN" : "USER");
    setEditUserStartAddress(u.start_address || "");
  }, [editUserId, users]);


   const saveBatchSettings = async () => {
    try {
      const [hh] = batchSettings.rolloverAt.split(":");
      const hour = parseInt(hh, 10);
      if (Number.isNaN(hour) || hour < 0 || hour > 23) {
        alert("Please enter a valid hour between 00:00 and 23:59");
        return;
      }

      await API("/api/settings/batch", {
        method: "POST",
        body: JSON.stringify({
          rollover_hour: hour,
          rollover_timezone: batchSettings.timezone || "Europe/London",
        }),
      });

      localStorage.setItem("batchSettings", JSON.stringify(batchSettings));
      alert(
        "Rollover time updated – not-done tasks will be moved at this time in the selected timezone."
      );
    } catch (e) {
      alert(e?.message || "Failed to save batch settings");
    }
  };



  const createStudent = async () => {
    if (!studentName.trim()) {
      alert("Student name is required");
      return;
    }
    try {
      await API("/api/students", {
        method: "POST",
        body: JSON.stringify({
          name: studentName.trim(),
          student_class: studentClass.trim() || null,
          address: studentAddress.trim() || null,
        }),
      });
      setStudentName("");
      setStudentClass("");
      setStudentAddress("");
      const st = await API("/api/students");
      setStudents(st || []);
      alert("Student created");
    } catch (e) {
      alert(e?.message || "Failed to create student");
    }
  };

  const deleteStudent = async () => {
    if (!deleteStudentId) return;
    if (!confirm(`Delete student #${deleteStudentId}?`)) return;
    try {
      await API(`/api/students/${deleteStudentId}`, { method: "DELETE" });
      const st = await API("/api/students");
      setStudents(st || []);
      setDeleteStudentId("");
      alert("Student deleted");
    } catch (e) {
      alert(e?.message || "Failed to delete student");
    }
  };

const createUser = async () => {
  if (!userName.trim() || !userEmail.trim() || !userPassword.trim()) {
    alert("Name, email and password are required");
    return;
  }

  // very simple email validation to avoid 422 from backend
  if (!userEmail.includes("@") || !userEmail.includes(".")) {
    alert("Please enter a valid email address (e.g. user@example.com)");
    return;
  }

  // Map UI role ("USER"/"ADMIN") to backend enum ("User"/"Admin")
  const backendRole =
    userRole === "ADMIN" || userRole === "Admin" ? "Admin" : "User";

  try {
    await API("/api/users", {
      method: "POST",
      body: JSON.stringify({
        name: userName.trim(),
        email: userEmail.trim().toLowerCase(),
        role: backendRole,
        password: userPassword.trim(),
      }),
    });

    setUserName("");
    setUserEmail("");
    setUserPassword("");

    const us = await API("/api/users");
    setUsers(us || []);
    alert("User created");
  } catch (e) {
    alert(e?.message || "Failed to create user");
  }
};




  const deleteUser = async () => {
    if (!deleteUserId) return;
    if (!confirm(`Delete user #${deleteUserId}?`)) return;
    try {
      await API(`/api/users/${deleteUserId}`, { method: "DELETE" });
      const us = await API("/api/users");
      setUsers(us || []);
      setDeleteUserId("");
      alert("User deleted");
    } catch (e) {
      alert(e?.message || "Failed to delete user");
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        style={{ maxWidth: 520 }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3>Settings</h3>

        <div className="chipbar">
          <button
            className={`chip ${tab === "batch" ? "active" : ""}`}
            onClick={() => setTab("batch")}
          >
            Batch times
          </button>
          <button
            className={`chip ${tab === "users" ? "active" : ""}`}
            onClick={() => setTab("users")}
          >
            Users
          </button>
        </div>

{tab === "batch" && (
  <>
    <p className="help">
      This time controls when all not-done tasks for today will be moved
      automatically to tomorrow (same as “Move to next day”). Time is applied
      in the selected timezone.
    </p>

    <label className="label">Move not-done tasks at</label>
    <select
      className="input"
      value={batchSettings.rolloverAt}
      onChange={(e) =>
        setBatchSettings((s) => ({ ...s, rolloverAt: e.target.value }))
      }
    >
      {Array.from({ length: 24 }).map((_, h) => {
        const label = `${String(h).padStart(2, "0")}:00`;
        return (
          <option key={h} value={label}>
            {label}
          </option>
        );
      })}
    </select>

    <label className="label" style={{ marginTop: 8 }}>
      Timezone
    </label>
    <select
      className="input"
      value={batchSettings.timezone}
      onChange={(e) =>
        setBatchSettings((s) => ({ ...s, timezone: e.target.value }))
      }
    >
      {TIMEZONES.map((tz) => (
        <option key={tz.value} value={tz.value}>
          {tz.label}
        </option>
      ))}
    </select>

    <div className="btns" style={{ marginTop: 12 }}>
      <button className="btn" onClick={onClose}>
        Close
      </button>
      <button className="btn btn-primary" onClick={saveBatchSettings}>
        Save
      </button>
    </div>
  </>
)}



        {tab === "users" && (
          <>
            <label className="label">Name</label>
<input
  className="input"
  value={userName}
  onChange={(e) => setUserName(e.target.value)}
/>

<label className="label">Email</label>
<input
  className="input"
  value={userEmail}
  onChange={(e) => setUserEmail(e.target.value)}
/>

<label className="label">Password</label>
<input
  className="input"
  type="password"
  value={userPassword}
  onChange={(e) => setUserPassword(e.target.value)}
/>

<label className="label">Role</label>
<select
  className="select"
  value={userRole}
  onChange={(e) => setUserRole(e.target.value)}
>
  <option value="USER">User</option>
  <option value="ADMIN">Admin</option>
</select>


            <div className="btns" style={{ marginTop: 8 }}>
              <button className="btn" onClick={createUser}>
                Create user
              </button>
            </div>

            <hr style={{ margin: "16px 0" }} />

            <label className="label">Delete user</label>
            <select
  className="select"
  value={deleteUserId}
  onChange={(e) => setDeleteUserId(Number(e.target.value))}
>
  <option value="">Select…</option>
  {users
    .filter(
      (u) => u.role !== "Admin" && u.role !== "ADMIN" // ikke list admin for delete
    )
    .map((u) => (
      <option key={u.id} value={u.id}>
        #{u.id} {u.name} ({u.role})
      </option>
    ))}
</select>


            <div className="btns" style={{ marginTop: 8 }}>
              <button className="btn btn-danger" onClick={deleteUser}>
                Delete selected
              </button>
            </div>

<hr style={{ margin: "16px 0" }} />

<label className="label">Change role</label>
<select
  className="select"
  value={editUserId}
  onChange={(e) => setEditUserId(e.target.value)}
>
  <option value="">Select user…</option>
  {users.map((u) => (
    <option key={u.id} value={u.id}>
      #{u.id} {u.name} ({u.role})
    </option>
  ))}
</select>

<label className="label" style={{ marginTop: 8 }}>New role</label>
<select
  className="select"
  value={editUserRole}
  onChange={(e) => setEditUserRole(e.target.value)}
>
  <option value="USER">User</option>
  <option value="ADMIN">Admin</option>
</select>

<label className="label" style={{ marginTop: 8 }}>Start address</label>
<input
  className="input"
  value={editUserStartAddress}
  onChange={(e) => setEditUserStartAddress(e.target.value)}
  placeholder="Optional default start address"
/>

<div className="btns" style={{ marginTop: 8 }}>
  <button
    className="btn"
    onClick={async () => {
      if (!editUserId) return;

      const backendRole =
        editUserRole === "ADMIN" || editUserRole === "Admin"
          ? "Admin"
          : "User";

      try {
        await API(`/api/users/${editUserId}`, {
          method: "PATCH",
          body: JSON.stringify({
            role: backendRole,
            start_address: editUserStartAddress.trim() || null,
          }),
        });

        const us = await API("/api/users");
        setUsers(us || []);

        // 🔄 Oppdater innlogget bruker i localStorage også
        try {
          const me = await API("/api/me");
          localStorage.setItem("current_user", JSON.stringify(me));
        } catch {
          // ignore, route funker uansett etter reload
        }

        alert("User updated");
      } catch (e) {
        alert(e?.message || "Failed to update user");
      }
    }}
  >
    Update user
  </button>
</div>



            <div className="meta" style={{ marginTop: 8, fontSize: 12 }}>
              Total users: {users.length}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
/* =========================== END BLOCK =========================== */

function ProfileSettingsModal({ onClose }) {
  const [startAddress, setStartAddress] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    API("/api/me")
      .then((me) => {
        if (me) {
          setStartAddress(me.start_address || "");
          localStorage.setItem("current_user", JSON.stringify(me));
        }
      })
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const updated = await API("/api/me", {
        method: "PATCH",
        body: JSON.stringify({
          start_address: startAddress.trim(),
        }),
      });
      localStorage.setItem("current_user", JSON.stringify(updated));
      alert("Saved");
      onClose();
    } catch (e) {
      alert(e?.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        style={{ maxWidth: 480 }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3>My settings</h3>

        <p className="help">
          Set your default starting address. All route maps and Smart Route
          will start from this address in Google Maps.
        </p>

        <label className="label">Start address</label>
        <input
          className="input"
          value={startAddress}
          onChange={(e) => setStartAddress(e.target.value)}
          placeholder="e.g. London or home address"
        />

        <div className="btns" style={{ marginTop: 12 }}>
          <button className="btn" onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </button>
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}


/* ================================================================
   BLOCK: COMMENTS / HISTORY / CREATE / EDIT
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
          <li key={c.id} className="comment-row">
            <span className="comment-author">{c.author || "User"}</span>
            <span className="comment-date">
              {new Date(c.created_at).toLocaleString("no-NO")}
            </span>
            <div className="comment-text">{c.text}</div>
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

function HistoryModal({ studentId, onClose }) {
  const [student, setStudent] = useState(null);

  // Hent alle elever og finn den ene vi trenger
  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const allStudents = await API("/api/students");
        if (cancelled) return;

        const sid = Number(studentId);
        const s = (allStudents || []).find((st) => st.id === sid);
        setStudent(s || null);
      } catch {
        if (!cancelled) setStudent(null);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [studentId]);

  // ESC lukker modalen
  useEffect(() => {
    const onEsc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [onClose]);

  const fmtPct = (val) =>
    val == null || Number.isNaN(Number(val))
      ? "–"
      : `${Number(val).toFixed(1)}%`;

  const attendanceYtd =
    student?.attendance_ytd ?? student?.attendance_pct ?? null;
  const absenceYtd =
    attendanceYtd != null ? Math.max(0, 100 - attendanceYtd) : null;

  const lastWeek = student?.attendance_last_week ?? null;
  const last2Weeks = student?.attendance_last_2_weeks ?? null;
  const last3Weeks = student?.attendance_last_3_weeks ?? null;
  const last4Weeks = student?.attendance_last_4_weeks ?? null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Student history</h3>

        {student && (
          <div className="card student-card">
            <div className="student-card-header">
              <div>
                <div className="student-card-name">{student.name}</div>
                <div className="student-card-sub">
                  Year: {student.student_class ?? "–"}
                  {student.gender && <> · Gender: {student.gender}</>}
                </div>
              </div>
              <div className="student-chip">
                {attendanceYtd != null ? fmtPct(attendanceYtd) : "No YtD data"}
              </div>
            </div>

            <div className="student-meta-row">
              <span className="student-meta-label">Address</span>
              <span className="student-meta-value">
                {student.address || "Not set"}
              </span>
            </div>

            <div className="student-meta-row">
              <span className="student-meta-label">Contact</span>
              <span className="student-meta-value">
                {student.contact_name || "–"}
                {student.contact_relationship
                  ? ` (${student.contact_relationship})`
                  : ""}
                {student.contact_phone ? ` · ${student.contact_phone}` : ""}
              </span>
            </div>

            <div className="student-meta-row">
              <span className="student-meta-label">Absent today</span>
              <span className="student-meta-value">
                <span
                  className={
                    student.absent_today ? "pill pill-danger" : "pill pill-ok"
                  }
                >
                  {student.absent_today ? "Yes" : "No"}
                </span>
              </span>
            </div>

            <div className="student-grid">
              <div className="student-stat">
                <div className="student-stat-label">Attendance YtD</div>
                <div className="student-stat-value">
                  {fmtPct(attendanceYtd)}
                </div>
              </div>
              <div className="student-stat">
                <div className="student-stat-label">Absence YtD</div>
                <div className="student-stat-value">
                  {absenceYtd != null ? fmtPct(absenceYtd) : "–"}
                </div>
              </div>
              <div className="student-stat">
                <div className="student-stat-label">Last week</div>
                <div className="student-stat-value">
                  {fmtPct(lastWeek)}
                </div>
              </div>
              <div className="student-stat">
                <div className="student-stat-label">Last 2 weeks</div>
                <div className="student-stat-value">
                  {fmtPct(last2Weeks)}
                </div>
              </div>
              <div className="student-stat">
                <div className="student-stat-label">Last 3 weeks</div>
                <div className="student-stat-value">
                  {fmtPct(last3Weeks)}
                </div>
              </div>
              <div className="student-stat">
                <div className="student-stat-label">Last 4 weeks</div>
                <div className="student-stat-value">
                  {fmtPct(last4Weeks)}
                </div>
              </div>
            </div>

            <div className="student-events-summary">
              Data is imported daily from the school system and reflects
              attendance per student.
            </div>
          </div>
        )}

        <div className="btns" style={{ marginTop: 12 }}>
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}


function CreateModal({ defaultAssigneeId = 2, onClose, onCreated }) {
  const [students, setStudents] = useState([]);
  const [studentId, setStudentId] = useState("");
  const [title, setTitle] = useState("");
  const [address, setAddress] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // 👇 NYTT: finn valgt student
  const selectedStudent = useMemo(
    () => students.find((s) => s.id === Number(studentId)),
    [students, studentId]
  );

  useEffect(() => {
    API("/api/students")
      .then(setStudents)
      .catch(() => setStudents([]));
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

  // 👇 NYTT: auto-fyll adresse + tittel når student endres
  useEffect(() => {
    if (!selectedStudent) return;

    setAddress((prev) => (prev ? prev : selectedStudent.address || ""));
    setTitle((prev) =>
      prev ? prev : `Home visit for ${selectedStudent.name}`
    );
  }, [selectedStudent]);


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
    due_at: defaultDueAt(),           // 👈 her
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
              {s.name} {s.student_class ? `(${s.student_class})` : ""}
            </option>
          ))}
        </select>

        <label className="label">Title</label>
        <input
          className="input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        <label className="label">Address</label>
        <input
          className="input"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
        />

        <label className="label">Reason</label>
        <textarea
          className="textarea"
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />

        <div className="meta" style={{ marginTop: 8, opacity: 0.8 }}>
          {new Date().toLocaleDateString("no-NO")}
        </div>

        <div className="btns" style={{ marginTop: 12 }}>
          <button className="btn" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={createTask}
            disabled={saving}
          >
            {saving ? "Creating..." : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EditModal({ task, onClose, onSaved, isAdmin }) {
  const [title, setTitle] = useState(task.title);
  const [address, setAddress] = useState(task.address || "");
  const [dueAt, setDueAt] = useState(
    onlyDateStr(task.due_at || defaultDueAt())
  );
  const [reason, setReason] = useState(getReason(task));
  const [assignee, setAssignee] = useState(task.assignee_user_id || 2);

  const [checklist, setChecklist] = useState(
    Array.isArray(task.checklist) ? task.checklist : []
  );
  const [newItem, setNewItem] = useState("");

  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [users, setUsers] = useState([]);

  useEffect(() => {
    if (!isAdmin) return;

    API("/api/users")
      .then((data) => {
        setUsers(data || []);
      })
      .catch(() => {
        setUsers([]);
      });
  }, [isAdmin]);


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

if (isAdmin) {
  payloadBase.assignee_user_id = Number(assignee);
  payloadBase.external_ref = task.external_ref ?? null;
}


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
            className="btn ghost"
            onClick={onClose}
            aria-label="Close"
            title="Close"
          >
            ×
          </button>
        </div>

        {err && <div className="alert error">{err}</div>}

        <label className="label">Title</label>
        <input
          className="input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        <label className="label">Address</label>
        <input
          className="input"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
        />

        <label className="label">Due date</label>
        <input
          type="date"
          className="input"
          value={dueAt || ""}
          onChange={(e) => setDueAt(e.target.value)}
        />

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
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    flex: 1,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={!!it.done}
                    onChange={() => toggleItem(i)}
                  />
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
                <button
                  className="btn btn-danger"
                  onClick={() => removeItem(i)}
                >
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
    <select
      className="select"
      value={assignee}
      onChange={(e) => setAssignee(Number(e.target.value))}
    >
      {users.map((u) => (
        <option key={u.id} value={u.id}>
          {u.name} ({u.email})
        </option>
      ))}
    </select>
  </div>
)}


        <div
          className="btns"
          style={{ marginTop: 12, gap: 8, flexWrap: "wrap" }}
        >
          <button className="btn" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button className="btn" onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </button>
          {isAdmin && (
            <button
              className="btn btn-primary"
              onClick={saveAndAssign}
              disabled={saving}
            >
              {saving ? "Working…" : "Save & Assign"}
            </button>
          )}
          {isAdmin && (
            <button
              className="btn btn-danger"
              onClick={deleteTask}
              disabled={saving}
            >
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
        document.dispatchEvent(
          new CustomEvent("task-synced", {
            detail: { id: t.id, status: "Done" },
          })
        );
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
  const onTs = (e) => {
    startX.current = e.touches[0].clientX;
  };
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
      className={`task ${compact ? "compact" : ""} ${
        t.status === "Rejected" ? "rejected" : ""
      }`}
      style={{ transform: `translateX(${dragX}px)` }}
      onTouchStart={onTs}
      onTouchMove={onTm}
      onTouchEnd={onTe}
    >
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="title">{t.title}</div>
        <div className="row" style={{ gap: 6 }}>
          {!!t.external_ref && <small className="badge">API</small>}
          <small
            className={`badge ${
              t.status === "Rejected" ? "rejected" : ""
            }`}
          >
            {t.status}
          </small>
        </div>
      </div>

      {!!reasonText && (
        <div className="mt-1">
          <div className="reason-label">REASON</div>
          <div
            className={`reason-text ${
              t.status === "Rejected" ? "red" : ""
            }`}
          >
            {reasonText}
          </div>
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
              `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                t.address || "London"
              )}`,
              "_blank"
            )
          }
        >
          Open in Maps
        </button>

        <button
          className="btn"
          onClick={() =>
            document.dispatchEvent(
              new CustomEvent("open-history", {
                detail: { studentId: t.student_id },
              })
            )
          }
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

              {isAdmin && (
          <button
            className="btn"
            onClick={async () => {
              try {
                // move task to next day, keep roughly same time (or 09:00 if none)
                const baseDate = t.due_at ? new Date(t.due_at) : new Date();
                baseDate.setDate(baseDate.getDate() + 1);
                baseDate.setHours(9, 0, 0, 0);

                await API(`/api/tasks/${t.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({
                    due_at: baseDate.toISOString(),
                    external_ref: t.external_ref ?? null,
                  }),
                });
                await reload();
              } catch (e) {
                alert(e?.message || "Failed to move task to next day");
              }
            }}
          >
            Move to next day
          </button>
        )}


        <button className="btn btn-primary" onClick={() => act("complete")}>
          DONE
        </button>

        {canEdit && (
          <button
            className="btn"
            onClick={() =>
              window.dispatchEvent(
                new CustomEvent("edit-task", { detail: { task: t } })
              )
            }
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
      <h3 className="col-title">{title}</h3>
      {list.map((t) => (
        <TaskCard
          key={t.id}
          t={t}
          reload={reload}
          compact={compact}
          meId={meId}
          isAdmin={isAdmin}
        />
      ))}
    </div>
  );
}
/* =========================== END BLOCK =========================== */

/* ================================================================
   BLOCK: ADMIN_BOARD / USER_BOARD
   ================================================================= */
function AdminBoard({ compact, tasks, reload, isAdmin, meId, query }) {
  const text = (query || "").toLowerCase();

  const tasksTextFiltered = useMemo(() => {
    if (!text) return tasks;
    return tasks.filter((t) => {
      const hay = `${t.title || ""} ${t.body || ""} ${
        t.address || ""
      }`.toLowerCase();
      return hay.includes(text);
    });
  }, [tasks, text]);

  const todayStr = new Date().toISOString().slice(0, 10);

  // ========================= USER VIEW =========================
  if (!isAdmin) {
    const [scope, setScope] = useState("today");
    const forMe = useMemo(
      () => tasksTextFiltered.filter((t) => t.assignee_user_id === meId),
      [tasksTextFiltered, meId]
    );

    const filtered = useMemo(() => {
      switch (scope) {
        case "today":
          return forMe.filter(
            (t) =>
              onlyDateStr(t.due_at) === todayStr &&
              t.status !== "Done" &&
              t.status !== "Rejected"
          );
        case "rejected":
          return forMe.filter((t) => t.status === "Rejected");
        case "done":
          return forMe.filter((t) => t.status === "Done");
        default:
          return forMe;
      }
    }, [forMe, scope, todayStr]);

    const sorted = useMemo(
      () =>
        filtered
          .slice()
          .sort((a, b) => ((a.due_at || "") > (b.due_at || "") ? 1 : -1)),
      [filtered]
    );

    return (
      <>
        <div className="chipbar">
          <button
            className={`chip ${scope === "today" ? "active" : ""}`}
            onClick={() => setScope("today")}
          >
            Today
          </button>
          <button
            className={`chip ${scope === "rejected" ? "active" : ""}`}
            onClick={() => setScope("rejected")}
          >
            Rejected
          </button>
          <button
            className={`chip ${scope === "done" ? "active" : ""}`}
            onClick={() => setScope("done")}
          >
            Done
          </button>
        </div>
        <div className="board">
          <Column
            title={
              scope === "today"
                ? "Today"
                : scope === "rejected"
                ? "Rejected"
                : "Done"
            }
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

  // ========================= ADMIN VIEW =========================
  const [view, setView] = useState("overview"); // overview | perUser
  const [userFilter, setUserFilter] = useState("");
  const [selectedDate, setSelectedDate] = useState(todayStr);
const [statusScope, setStatusScope] = useState("today"); // today | rejected | done

  const tasksByDate = useMemo(() => {
    if (!selectedDate) return tasksTextFiltered;
    const key = selectedDate;
    return tasksTextFiltered.filter((t) => {
      if (!t.due_at) return false;
      return onlyDateStr(t.due_at) === key;
    });
  }, [tasksTextFiltered, selectedDate]);

  const usersFromTasks = useMemo(() => {
    const map = new Map();
    for (const t of tasksByDate) {
      if (t.assignee_user_id != null) {
        map.set(t.assignee_user_id, `User ${t.assignee_user_id}`);
      }
    }
    for (const u of USERS) {
      if (map.has(u.id)) map.set(u.id, u.name);
    }
    return Array.from(map.entries()).sort((a, b) =>
      String(a[1]).localeCompare(String(b[1]))
    );
  }, [tasksByDate]);

  const sorted = useMemo(
    () =>
      tasksByDate
        .slice()
        .sort((a, b) => ((a.due_at || "") > (b.due_at || "") ? 1 : -1)),
    [tasksByDate]
  );

  const statusMatchesScope = (t) => {
    switch (statusScope) {
      case "today":
        return t.status !== "Done" && t.status !== "Rejected";
      case "rejected":
        return t.status === "Rejected";
      case "done":
        return t.status === "Done";
      default:
        return true;
    }
  };


  const candidateTasks = useMemo(
    () =>
      sorted.filter(
        (t) =>
          onlyDateStr(t.due_at) === todayStr &&
          t.status !== "Done" &&
          t.status !== "Rejected"
      ),
    [sorted, todayStr]
  );

  const tasksForSelectedUserToday = useMemo(() => {
    if (view !== "perUser" || !userFilter) return [];
    return tasksTextFiltered.filter(
      (t) =>
        String(t.assignee_user_id) === String(userFilter) &&
        onlyDateStr(t.due_at) === todayStr &&
        t.status !== "Done" &&
        t.status !== "Rejected"
    );
  }, [view, userFilter, tasksTextFiltered, todayStr]);

  const selectedUserName =
    usersFromTasks.find(([id]) => String(id) === String(userFilter))?.[1] ||
    (userFilter ? `User ${userFilter}` : "");

    const col = (title, filter) => (
    <Column
      title={title}
      filter={(t) => statusMatchesScope(t) && filter(t)}
      tasks={sorted}
      reload={reload}
      compact={compact}
      meId={meId}
      isAdmin={true}
    />
  );


  const handleExportCsv = () => {
    let rows = tasksByDate;
    if (view === "perUser" && userFilter) {
      rows = rows.filter(
        (t) => String(t.assignee_user_id) === String(userFilter)
      );
    }
    if (!rows || rows.length === 0) {
      alert("No tasks to export for current filters");
      return;
    }

    const header = [
      "ID",
      "Title",
      "Status",
      "AssigneeId",
      "DueDate",
      "StudentId",
      "Address",
      "AttendancePct",
      "LastAbsenceDate",
      "LastAbsenceReason",
    ];

    const escapeCell = (val) => {
      if (val === null || val === undefined) return "";
      const s = String(val);
      if (s.includes(",") || s.includes('"') || s.includes("\n")) {
        return '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    };

    const lines = [header.join(",")];
    for (const t of rows) {
      lines.push(
        [
          t.id,
          t.title || "",
          t.status || "",
          t.assignee_user_id ?? "",
          t.due_at || "",
          t.student_id ?? "",
          t.address || "",
          typeof t.attendance_pct === "number" ? t.attendance_pct : "",
          t.last_absence_date || "",
          t.last_absence_reason || "",
        ]
          .map(escapeCell)
          .join(",")
      );
    }

    const csv = lines.join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tasks_export.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="filterbar">
        <label className="inline no-shrink">
          View
          <select
            className="select-sm"
            value={view}
            onChange={(e) => setView(e.target.value)}
          >
            <option value="overview">Overview</option>
            <option value="perUser">Per user</option>
          </select>
        </label>

        <label className="inline no-shrink">
          Date
          <input
            type="date"
            className="select-sm"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          />
        </label>

        <button
          type="button"
          className="chip chip-today"
          onClick={() => setSelectedDate(todayStr)}
        >
          Today
        </button>

        {view === "perUser" && (
          <label className="inline no-shrink">
            User
            <select
              className="select-sm"
              value={userFilter}
              onChange={(e) => setUserFilter(e.target.value)}
            >
              <option value="">(select user)</option>
              {usersFromTasks.map(([id, name]) => (
                <option key={id} value={String(id)}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        )}

              <div className="spacer" />

        <div className="chipbar chipbar-inline">
          <button
            type="button"
            className={`chip ${statusScope === "today" ? "active" : ""}`}
            onClick={() => setStatusScope("today")}
          >
            Today
          </button>
          <button
            type="button"
            className={`chip ${statusScope === "rejected" ? "active" : ""}`}
            onClick={() => setStatusScope("rejected")}
          >
            Rejected
          </button>
          <button
            type="button"
            className={`chip ${statusScope === "done" ? "active" : ""}`}
            onClick={() => setStatusScope("done")}
          >
            Done
          </button>
        </div>

        <button type="button" className="btn" onClick={handleExportCsv}>
          Export CSV
        </button>
      </div>


      {selectedDate === todayStr && (
        <div className="info-row">
          {candidateTasks.length ? (
            <>
              <strong>{candidateTasks.length}</strong> tasks not done today –
              candidates for tomorrow.
            </>
          ) : (
            <>No open tasks for today. 🎉</>
          )}
        </div>
      )}

      {/* ✅ Admin route map when viewing a single user's tasks */}
      {view === "perUser" && userFilter && (
        <RouteMapPanel
          tasks={tasksForSelectedUserToday}
          title={`Today's route for ${selectedUserName}`}
          subtitle="Based on today's active visits"
        />
      )}

      {view === "overview" ? (
        <div className="board">
          {col(
            "Today",
            (t) => t.status !== "Done" && t.status !== "Rejected"
          )}
          {col("Rejected", (t) => t.status === "Rejected")}
          {col("Done", (t) => t.status === "Done")}
        </div>
      ) : (
        <div className="board">
          {userFilter ? (
            <>
              {col(
                "Today",
                (t) =>
                  String(t.assignee_user_id) === String(userFilter) &&
                  t.status !== "Done" &&
                  t.status !== "Rejected"
              )}
              {col(
                "Rejected",
                (t) =>
                  String(t.assignee_user_id) === String(userFilter) &&
                  t.status === "Rejected"
              )}
              {col(
                "Done",
                (t) =>
                  String(t.assignee_user_id) === String(userFilter) &&
                  t.status === "Done"
              )}
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
   BLOCK: ROUTE_MAP + ROUTE_TAB
   ================================================================= */
function RouteMapPanel({ tasks, title, subtitle, startAddress }) {
  const sorted = useMemo(
    () =>
      (tasks || [])
        .slice()
        .sort((a, b) => new Date(a.due_at) - new Date(b.due_at)),
    [tasks]
  );

  // bare stoppene, ingen startAddress her
  const stops = useMemo(
    () => sorted.map((t) => t.address).filter(Boolean),
    [sorted]
  );

  const start = (startAddress || "").trim();

  // 🗺️ full map → device position origin
  const mapUrl = buildSmartRouteUrl(stops);

  // 🧭 embed → use start (or first stop) as origin
  const embedUrl = buildSmartRouteEmbedUrl(stops, start || undefined);

  const stopCount = sorted.length;
  const first = sorted[0];
  const last = sorted[sorted.length - 1];

  return (
    <section className="route-layout">
      <div className="route-map card route-map-card">
        {/* ... header etc ... */}
        {mapUrl && (
          <button
            className="btn btn-primary"
            onClick={() => window.open(mapUrl, "_blank")}
          >
            Open full map
          </button>
        )}
        {embedUrl ? (
          <div className="route-map-frame-wrap">
            <iframe
              src={embedUrl}
              title="Route map"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
              className="route-map-frame"
            />
          </div>
        ) : (
          <div className="route-map-empty">Google map will come in future</div>
        )}
      </div>

      <div className="route-list card">
        <div className="route-list-title">Stops</div>
        {!sorted.length && (
          <div className="route-map-empty">No visits for this route.</div>
        )}
        {sorted.map((t, idx) => (
          <div key={t.id} className="route-list-task">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <div className="route-list-task-title">
                  {idx + 1}. {t.title}
                </div>
                <div className="route-list-task-meta">
                  {fmtNO(t.due_at)} • {t.address || "-"}
                </div>
              </div>
              <span className="badge">{t.status}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function RouteTab({ tasksForMeToday, startAddress }) {
  return (
    <div className="route-tab">
      <RouteMapPanel
        tasks={tasksForMeToday}
        title="Today's route"
        subtitle="Your planned visits"
        startAddress={startAddress}
      />
    </div>
  );
}

/* =========================== END BLOCK =========================== */

/* ================================================================
   BLOCK: BOTTOM_NAV
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
   BLOCK: APP SHELL
   ================================================================= */
function App() {
  const [compact] = useState(true);
  const [activeTab, setActiveTab] = useState("board");
  const [authed, setAuthed] = useState(
    !!localStorage.getItem("auth_token") && !!localStorage.getItem("x_user")
  );
  const [showCreate, setShowCreate] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const { tasks, reload } = useTasks();

  const path = window.location.pathname;
  useEffect(() => {
    if (!authed && path !== "/login") window.location.replace("/login");
    if (authed && path === "/login") window.location.replace("/");
  }, [authed, path]);

  if (!authed) return <Login onLoggedIn={() => setAuthed(true)} />;

  let currentUser = null;
  try {
    currentUser = JSON.parse(localStorage.getItem("current_user") || "null");
  } catch {
    currentUser = null;
  }

  const meId = currentUser?.id ?? 0;
  const isAdmin =
    currentUser?.role === "ADMIN" ||
    currentUser?.role === "Admin" ||
    currentUser?.role === "admin";

  useEffect(() => {
    document.body.classList.toggle("is-admin", isAdmin);
  }, [isAdmin]);

  const todayISO = new Date().toISOString().slice(0, 10);
  const myAssigned = (tasks || []).filter(
    (t) => t.assignee_user_id === meId && t.status !== "Done" && t.due_at
  );
  const tasksForMeToday = myAssigned.filter(
    (t) => onlyDateStr(t.due_at) === todayISO
  );

const openSmartRoute = () => {
  if (!tasksForMeToday.length) return;

  const stops = tasksForMeToday.map((t) => t.address).filter(Boolean);
  const url = buildSmartRouteUrl(stops); // 👈 no startAddress here
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

  const [q, setQ] = useState("");

  return (
    <>
      <Header
        onOpenSmartRoute={openSmartRoute}
        todaysCount={tasksForMeToday.length}
        onCreate={() => setShowCreate(true)}
        isAdmin={isAdmin}
        onOpenSettings={() => setShowSettings(true)}
      />

      <div className="search-strip">
        <SearchBar value={q} onChange={setQ} />
      </div>

      <div className="tabs">
        <div className="tabs-left">
          <button
            className={activeTab === "board" ? "tab active" : "tab"}
            onClick={() => setActiveTab("board")}
          >
            Board
          </button>
          {!isAdmin && (
            <button
              className={activeTab === "route" ? "tab active" : "tab"}
              onClick={() => setActiveTab("route")}
            >
              Route
            </button>
          )}
        </div>

   <div className="tabs-right">
  <button
   className="tab link no-shrink"
    onClick={reload}
  >
    ↻ Refresh
  </button>

  <button
    className="tab link no-shrink"
    onClick={() => setShowCreate(true)}
  >
    + New task
  </button>
</div>


      </div>

      {activeTab === "board" ? (
  <AdminBoard
    compact={compact}
    tasks={tasks}
    reload={reload}
    isAdmin={isAdmin}
    meId={meId}
    query={q}
  />
) : (
  <RouteTab
    tasksForMeToday={tasksForMeToday}
    startAddress={currentUser?.start_address || ""}
  />
)}


      {showCreate && (
        <CreateModal
          defaultAssigneeId={meId}  
          onClose={() => setShowCreate(false)}
          onCreated={reload}
        />
      )}

      {showSettings &&
  (isAdmin ? (
    <SettingsModal onClose={() => setShowSettings(false)} />
  ) : (
    <ProfileSettingsModal onClose={() => setShowSettings(false)} />
  ))}


      {editTask && (
        <EditModal
          task={editTask}
          onClose={() => setEditTask(null)}
          onSaved={reload}
          isAdmin={isAdmin}
        />
      )}

      {historyStudentId && (
        <HistoryModal
          studentId={historyStudentId}
          onClose={() => setHistoryStudentId(null)}
        />
      )}

      <BottomNav onBack={goBack} onHome={goHome} onOverview={goOverview} />
    </>
  );
}
/* =========================== END BLOCK =========================== */

createRoot(document.getElementById("root")).render(<App />);
