import React, {useEffect, useMemo, useState} from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

// Feature flags
const FLAGS = {
  dnd: true,
  bulk: true,
  filters: true,
  modernTheme: true
};

const API = (path, opts={}) => fetch(`http://localhost:8000${path}`, {
  headers: { "X-User": localStorage.getItem("user") || "anna", "Content-Type":"application/json" },
  ...opts
}).then(async r => { if(!r.ok){ throw new Error(await r.text() || r.statusText) } return r.json() })

// ---------- Helpers ----------
function onlyDateStr(d){
  try{
    const dt = new Date(d);
    return isNaN(dt) ? null : dt.toISOString().slice(0,10);
  }catch{return null}
}
function buildSmartRouteUrl(addresses){
  if(!addresses || addresses.length===0) return null;
  const enc = s => encodeURIComponent(s||'London');
  if(addresses.length===1){
    return `https://www.google.com/maps/dir/?api=1&destination=${enc(addresses[0])}`;
  }
  const dest = enc(addresses[addresses.length-1]);
  const waypoints = addresses.slice(0,-1).map(enc).join('|');
  return `https://www.google.com/maps/dir/?api=1&travelmode=driving&destination=${dest}&waypoints=${waypoints}`;
}
function minutes(n){ return Math.round(n) }
function estimateDurations(stops){
  // Fallback: assume 15m per stop + 12m travel between stops
  const perStop = 15; const perHop = 12;
  const total = stops.length*perStop + Math.max(0, stops.length-1)*perHop
  return { totalMinutes: total, perStop, perHop }
}

// ---------- Auth / Login ----------
function Login({onDemoLogin, onGoogleLogin}){
  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="brand">Simple Task Pro</div>
        <div className="sub">Sign in to continue</div>
        <div className="field">
          <div className="label">Demo login</div>
          <div style={{display:'grid', gap:8}}>
            <button className="btn" onClick={()=>onDemoLogin('anna')}>Continue as Anna (Admin)</button>
            <button className="btn" onClick={()=>onDemoLogin('ulf')}>Continue as Ulf (User 1)</button>
            <button className="btn" onClick={()=>onDemoLogin('una')}>Continue as Una (User 2)</button>
          </div>
        </div>
        <div className="divider">or</div>
        <button className="oauth-btn" onClick={onGoogleLogin}>Continue with Google</button>
        <div className="sub" style={{marginTop:10,fontSize:12}}>Tip: Google Sign-In requires backend OAuth config.</div>
      </div>
    </div>
  )
}

// ---------- Common UI ----------
function Header({compact, setCompact, onOpenSmartRoute, todaysCount}) {
  const [me,setMe]=useState(null)
  useEffect(()=>{ API('/api/me').then(setMe).catch(()=>{}) },[])
  return (
    <div className="app-header">
      <div className="app-title">Simple Task Pro</div>
      <div className="spacer"/>
      <label style={{display:'flex',alignItems:'center',gap:8}}>
        <span style={{opacity:.8}}>Act as:</span>
        <select className="select" value={localStorage.getItem("user")||"anna"} onChange={(e)=>{localStorage.setItem("user", e.target.value); location.reload()}}>
          <option value="anna">Anna (Admin)</option>
          <option value="ulf">Ulf (User 1)</option>
          <option value="una">Una (User 2)</option>
        </select>
      </label>
      <div style={{opacity:.8, marginLeft:10}}>{me ? `${me.name} • ${me.role}` : ''}</div>
      <div style={{display:'flex', alignItems:'center', gap:8, marginLeft:12}}>
        <button className="btn" onClick={()=>setCompact(!compact)}>{compact ? "Compact: ON" : "Compact: OFF"}</button>
        <button className="btn btn-primary" onClick={onOpenSmartRoute}>Smart Route (today){todaysCount!==null ? ` • ${todaysCount}` : ""}</button>
      </div>
    </div>
  )
}

function useTasks(){
  const [tasks,setTasks]=useState([])
  const reload = ()=>API('/api/tasks').then(setTasks).catch(()=>setTasks([]))
  useEffect(reload,[])
  return {tasks, reload}
}

function FilterBar({setQuery, setStatus, setUser, bulkMode, setBulkMode}){
  if(!FLAGS.filters && !FLAGS.bulk) return null
  return (
    <div className="filterbar">
      {FLAGS.filters && (<>
        <input className="input" placeholder="Search student/title/address..." onChange={e=>setQuery(e.target.value.toLowerCase())} />
        <select className="select-sm" onChange={e=>setStatus(e.target.value)} defaultValue="">
          <option value="">All statuses</option>
          <option>New</option><option>Assigned</option><option>Accepted</option><option>Rejected</option><option>Done</option>
        </select>
        <select className="select-sm" onChange={e=>setUser(e.target.value)} defaultValue="">
          <option value="">All users</option>
          <option value="2">User 1 (Ulf)</option>
          <option value="3">User 2 (Una)</option>
          <option value="none">Unassigned</option>
        </select>
      </>)}
      {FLAGS.bulk && (
        <button className="btn" onClick={()=>setBulkMode(!bulkMode)}>{bulkMode ? "Exit Bulk" : "Bulk select"}</button>
      )}
    </div>
  )
}

// ---------- Edit Modal + Checklist ----------
function ChecklistEditor({items, setItems}){
  const addItem = ()=> setItems([...(items||[]), {text:'', done:false}])
  const removeItem = (idx)=> setItems(items.filter((_,i)=>i!==idx))
  const toggle = (idx)=> setItems(items.map((it,i)=> i===idx ? {...it, done: !it.done} : it))
  const update = (idx, val)=> setItems(items.map((it,i)=> i===idx ? {...it, text: val} : it))
  const move = (idx, dir)=> {
    const arr = items.slice(); const j = idx+dir;
    if(j<0 || j>=arr.length) return;
    [arr[idx], arr[j]] = [arr[j], arr[idx]]; setItems(arr);
  }
  return (
    <div>
      {(items||[]).map((it,idx)=>(
        <div key={idx} className="row" style={{gap:8, marginBottom:8}}>
          <button className="btn" onClick={()=>move(idx,-1)}>↑</button>
          <button className="btn" onClick={()=>move(idx,1)}>↓</button>
          <input className="input" value={it.text} onChange={e=>update(idx,e.target.value)} placeholder="Item text"/>
          <button className="btn" onClick={()=>toggle(idx)}>{it.done?'✓':'○'}</button>
          <button className="btn btn-danger" onClick={()=>removeItem(idx)}>Del</button>
        </div>
      ))}
      <button className="btn btn-primary" onClick={addItem}>Add item</button>
    </div>
  )
}

function EditModal({task, onClose, onSaved}){
  const [title,setTitle]=useState(task.title||'')
  const [body,setBody]=useState(task.body||'')
  const [address,setAddress]=useState(task.address||'')
  const [due,setDue]=useState(task.due_at||'')
  const [studentId,setStudentId]=useState(task.student_id||null)
  const [checklist,setChecklist]=useState(task.checklist||[])

  const save = async ()=>{
    const payload = { title, body, address, due_at: due||null, student_id: studentId, checklist }
    const res = await API(`/api/tasks/${task.id}`, {method:'PATCH', body: JSON.stringify(payload)})
    onSaved && onSaved(res)
    onClose()
  }

  return (
    <div className="modal-backdrop" onClick={(e)=>{ if(e.target.classList.contains('modal-backdrop')) onClose() }}>
      <div className="modal">
        <div className="row" style={{justifyContent:'space-between'}}>
          <h3>Edit Task</h3>
          <button className="btn" onClick={onClose}>Close</button>
        </div>
        <div className="field"><label className="label">Title</label><input className="input" value={title} onChange={e=>setTitle(e.target.value)} /></div>
        <div className="field"><label className="label">Notes</label><textarea className="textarea" value={body||''} onChange={e=>setBody(e.target.value)} /></div>
        <div className="field"><label className="label">Address</label><input className="input" value={address||''} onChange={e=>setAddress(e.target.value)} /></div>
        <div className="field"><label className="label">Due (ISO)</label><input className="input" placeholder="2025-10-19T10:00:00" value={due||''} onChange={e=>setDue(e.target.value)} /></div>
        <div className="field"><label className="label">Student ID</label><input className="input" value={studentId||''} onChange={e=>setStudentId(Number(e.target.value)||null)} /></div>

        <div className="field"><label className="label">Checklist</label><ChecklistEditor items={checklist||[]} setItems={setChecklist} /></div>
        <div className="row" style={{justifyContent:'flex-end', gap:8}}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={save}>Save</button>
        </div>
      </div>
    </div>
  )
}

// ---------- Task / Column / Bulk ----------
function TaskCard({t, reload, bulkMode, toggleSelect, selected, compact}){
  const [historyOpen,setHistoryOpen]=useState(false)
  const [history,setHistory]=useState([])
  const [showEdit,setShowEdit]=useState(false)
  const loadHistory=()=>API(`/api/students/${t.student_id}/history?days=90`).then(setHistory)
  const act = (action, reason) => API(`/api/tasks/${t.id}/status`, {method:'POST', body: JSON.stringify({action, reason})}).then(reload)

  const onDragStart = (e)=>{
    if(!FLAGS.dnd) return
    e.dataTransfer.setData('text/taskId', String(t.id))
  }

  const isAdmin = (localStorage.getItem("user")||"anna")==='anna'

  return (
    <div className={`task ${compact ? "compact" : ""}`} draggable={FLAGS.dnd} onDragStart={onDragStart}>
      <div className="row">
        <div className="title">{t.title}</div>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          {bulkMode && <input type="checkbox" className="checkbox" checked={!!selected} onChange={()=>toggleSelect(t.id)} />}
          <small className="badge">{t.status}</small>
        </div>
      </div>
      <div className="meta">Due: {t.due_at || '-'} • Address: {t.address || '-'}</div>
      <div className="btns">
        <button className="btn" onClick={()=>{setHistoryOpen(true); loadHistory();}}>History</button>
        {isAdmin && <button className="btn" onClick={()=>setShowEdit(true)}>Edit</button>}
        <button className="btn" onClick={()=>window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(t.address||'London')}`, '_blank')}>Open in Maps</button>
        <button className="btn" onClick={()=>act('accept')}>Accept</button>
        <button className="btn" onClick={()=>{ const r = prompt('Reject reason?'); if(r) act('reject', r) }}>Reject</button>
        <button className="btn btn-primary" onClick={()=>act('complete')}>Complete</button>
      </div>
      {isAdmin && showEdit && <EditModal task={t} onClose={()=>setShowEdit(false)} onSaved={reload} />}
      {historyOpen && (
        <div style={{marginTop:8, padding:10, background:'rgba(2,6,23,.5)', border:'1px solid var(--border)', borderRadius:12}}>
          <div className="row">
            <strong>Student history (last 90 days)</strong>
            <button className="btn" onClick={()=>setHistoryOpen(false)}>Close</button>
          </div>
          <ul>
            {history.map((h,i)=>(
              <li key={i} style={{color:'var(--muted)'}}>
                {h.kind==='absence' ? `[Absence] ${h.date} • ${h.reason_code} • ${h.reported_by} • ${h.note||''}`
                                    : `[Visit] ${h.date} • ${h.title}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Column({title, filter, dropAction, tasks, reload, bulkMode, selection, toggleSelect, compact}){
  const [dropping,setDropping]=useState(false)
  const list = tasks.filter(filter)

  const onDragOver = (e)=>{ if(FLAGS.dnd){ e.preventDefault(); setDropping(true) } }
  const onDragLeave = ()=> setDropping(false)
  const onDrop = async (e)=>{
    if(!FLAGS.dnd) return
    e.preventDefault(); setDropping(false)
    const id = Number(e.dataTransfer.getData('text/taskId'))
    if(!id) return
    await dropAction?.(id)
    reload()
  }

  return (
    <div className={dropping ? "col dropping" : "col"} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}>
      <h3>{title}</h3>
      <div className="drop-hint">Drop here</div>
      {list.map(t => (
        <TaskCard key={t.id} t={t} reload={reload} bulkMode={bulkMode} selected={selection.has(t.id)} toggleSelect={toggleSelect} compact={compact} />
      ))}
    </div>
  )
}

function BulkBar({selection, reload}){
  const ids = Array.from(selection)
  if(ids.length===0) return null

  const bulkAssign = async (assignee_user_id)=>{
    await Promise.all(ids.map(id => API(`/api/tasks/${id}/assign`, {method:'POST', body: JSON.stringify({assignee_user_id})})))
    reload()
  }
  const bulkComplete = async ()=>{
    await Promise.all(ids.map(id => API(`/api/tasks/${id}/status`, {method:'POST', body: JSON.stringify({action:'complete'})})))
    reload()
  }
  const bulkDelete = async ()=>{
    if(!confirm('Delete selected tasks?')) return
    await Promise.all(ids.map(id => fetch(`http://localhost:8000/api/tasks/${id}`, {method:'DELETE', headers: {"X-User": localStorage.getItem("user") || "anna"}})))
    reload()
  }

  return (
    <div className="bulkbar">
      <div style={{opacity:.8}}>Selected: {ids.length}</div>
      <button className="btn" onClick={()=>bulkAssign(2)}>Assign to Ulf</button>
      <button className="btn" onClick={()=>bulkAssign(3)}>Assign to Una</button>
      <button className="btn btn-primary" onClick={bulkComplete}>Mark Complete</button>
      <button className="btn btn-danger" onClick={bulkDelete}>Delete</button>
    </div>
  )
}

// ---------- Admin Board ----------
function AdminBoard({compact}){
  const {tasks, reload} = useTasks();

  // Single set of hooks
  const [query,setQuery]=useState("")
  const [status,setStatus]=useState("")
  const [user,setUser]=useState("")
  const [bulkMode,setBulkMode]=useState(false)
  const [selection,setSelection]=useState(new Set())

  const role = localStorage.getItem("user") || "anna"
  const meId = role==='ulf' ? 2 : (role==='una' ? 3 : 1)

  const todayISO = new Date().toISOString().slice(0,10)
  const myToday = tasks
    .filter(t => t.assignee_user_id===meId && t.due_at && onlyDateStr(t.due_at)===todayISO && t.status!=='Done')
    .sort((a,b)=> new Date(a.due_at) - new Date(b.due_at))

  const openSmartRoute = ()=>{
    const addrs = myToday.map(t=>t.address).filter(Boolean)
    const url = buildSmartRouteUrl(addrs)
    if(url) window.open(url, '_blank')
  }

  // expose globals for Header/App
  useEffect(()=>{
    window.__OPEN_SMART_ROUTE = openSmartRoute;
    window.__TODAYS_COUNT = myToday.length;
    window.__TODAYS_LIST = myToday;
    return ()=>{ window.__OPEN_SMART_ROUTE = null; window.__TODAYS_COUNT = null; window.__TODAYS_LIST = null; }
  }, [myToday]);

  const toggleSelect = (id)=>{
    const s = new Set(selection); s.has(id) ? s.delete(id) : s.add(id); setSelection(s)
  }

  const filtered = useMemo(()=>{
    return tasks.filter(t=>{
      if(query){
        const s = `${t.title}|${t.address||''}`.toLowerCase()
        if(!s.includes(query)) return false
      }
      if(status && t.status !== status) return false
      if(user){
        if(user==='none'){ if(t.assignee_user_id != null) return false }
        else if(String(t.assignee_user_id)!==String(user)) return false
      }
      return true
    })
  },[tasks, query, status, user])

  const col = (name, filter, dropAction)=>(
    <Column
      title={name}
      filter={filter}
      tasks={filtered}
      reload={reload}
      bulkMode={bulkMode}
      selection={selection}
      toggleSelect={toggleSelect}
      dropAction={dropAction}
      compact={compact}
    />
  )

  // DnD drop actions
  const assignTo = (uid)=> async (taskId)=> API(`/api/tasks/${taskId}/assign`, {method:'POST', body: JSON.stringify({assignee_user_id: uid})})
  const markDone = async (taskId)=> API(`/api/tasks/${taskId}/status`, {method:'POST', body: JSON.stringify({action:'complete'})})

  return (
    <>
      <FilterBar setQuery={setQuery} setStatus={setStatus} setUser={setUser} bulkMode={bulkMode} setBulkMode={setBulkMode} />
      <div className="board">
        {col("New", t=>t.status==='New', null)}
        {col("User 1", t=>t.status!=='Done' && t.assignee_user_id===2, assignTo(2))}
        {col("User 2", t=>t.status!=='Done' && t.assignee_user_id===3, assignTo(3))}
        {col("Done", t=>t.status==='Done', markDone)}
      </div>
      {FLAGS.bulk && <BulkBar selection={selection} reload={reload} />}
    </>
  )
}

// ---------- Route Tab ----------
function RouteTab({tasksForMeToday}){
  const sorted = tasksForMeToday.slice().sort((a,b)=> new Date(a.due_at) - new Date(b.due_at))
  const est = estimateDurations(sorted)
  const openSmartRoute = ()=>{
    const addrs = sorted.map(t=>t.address).filter(Boolean)
    const url = buildSmartRouteUrl(addrs)
    if(url) window.open(url, '_blank')
  }
  return (
    <div style={{padding:'8px 12px'}}>
      <div className="row" style={{justifyContent:'space-between', marginBottom:8}}>
        <div style={{opacity:.85}}>{sorted.length} visits today</div>
        <button className="btn btn-primary" onClick={openSmartRoute}>Open Smart Route</button>
      </div>
      <div style={{opacity:.8, marginBottom:10}}>Estimate ~ {minutes(est.totalMinutes)} min (incl. travel). Exact ETA in Google Maps.</div>
      {sorted.map((t,i)=>(
        <div key={t.id} className="task">
          <div className="row"><div className="title">{t.title}</div><small className="badge">{t.status}</small></div>
          <div className="meta">Due: {t.due_at || '-'} • Address: {t.address || '-'}</div>
          <div className="btns">
            <button className="btn" onClick={()=>window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(t.address||'London')}`, '_blank')}>Open in Maps</button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------- App ----------
function App(){
  const [compact,setCompact] = useState(false)
  const [activeTab,setActiveTab] = useState('board')
  const [authed,setAuthed]=useState(!!localStorage.getItem("user"))

  const onDemoLogin = (u)=>{ localStorage.setItem("user", u); setAuthed(true); }
  const onGoogleLogin = ()=>{ alert("Google Sign-In placeholder: configure OAuth backend first."); }

  // pull today's list from AdminBoard (globals) and keep in state for RouteTab
  const [tasksForMeToday, setTasksForMeToday] = useState([])
  useEffect(()=>{
    const update = ()=>{
      const arr = window.__TODAYS_LIST || []
      setTasksForMeToday(arr)
    }
    const t = setInterval(update, 500)
    update()
    return ()=> clearInterval(t)
  }, [])

  if(!authed){
    return <Login onDemoLogin={onDemoLogin} onGoogleLogin={onGoogleLogin} />
  }

  return (
    <>
      <Header compact={compact} setCompact={setCompact}
              onOpenSmartRoute={()=>window.__OPEN_SMART_ROUTE && window.__OPEN_SMART_ROUTE()}
              todaysCount={window.__TODAYS_COUNT ?? null} />
      <div className="tabs">
        <button className={activeTab==='board'?'tab active':'tab'} onClick={()=>setActiveTab('board')}>Board</button>
        <button className={activeTab==='route'?'tab active':'tab'} onClick={()=>setActiveTab('route')}>Route</button>
      </div>
      {activeTab==='board' ? <AdminBoard compact={compact}/> : <RouteTab tasksForMeToday={tasksForMeToday}/>}
    </>
  )
}

createRoot(document.getElementById('root')).render(<App/>)
