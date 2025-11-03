import { toTitleCase } from "@/utils/text";

export default function TaskCard({ task, onEdit, onAccept, onComplete, onReject }) {
  const openMaps = () => {
    if (!task?.address) return;
    window.open(`https://maps.google.com/?q=${encodeURIComponent(task.address)}`, "_blank");
  };

  return (
    <div className={`rounded-2xl border p-4 mb-4 ${task.status === "Rejected" ? "border-red-200 bg-red-50" : "border-slate-200 bg-white"}`}>
      <div className="flex items-start justify-between">
        <h3 className="font-semibold text-slate-800">{task.title}</h3>
        <span className={`ml-3 rounded-full px-2 py-0.5 text-xs ${task.status === "Rejected" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-700"}`}>
          {task.status}
        </span>
      </div>

      {/* REASON under Title */}
      {!!task.body && (
        <div className="mt-1">
          <div className="text-[11px] font-medium tracking-wide text-slate-500">REASON</div>
          <div className={`text-sm font-semibold ${task.status === "Rejected" ? "text-red-600" : "text-slate-700"}`}>
            {toTitleCase(task.body)}
          </div>
        </div>
      )}

      {/* meta row */}
      <div className="mt-2 text-sm text-slate-600">
        {task.due_at && <span>{new Date(task.due_at).toLocaleString()}</span>}
        {task.address && <span>{task.due_at ? " • " : ""}Address: {task.address}</span>}
      </div>

      {/* actions */}
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="rounded-xl border px-3 py-1 text-sm" onClick={openMaps}>Open in Maps</button>
        <button className="rounded-xl border px-3 py-1 text-sm" onClick={() => onAccept?.(task)}>Accept</button>
        <button className="rounded-xl bg-blue-600 text-white px-3 py-1 text-sm" onClick={() => onComplete?.(task)}>Complete</button>
        <button className="rounded-xl border px-3 py-1 text-sm" onClick={() => onEdit?.(task)}>Edit</button>
        {task.status !== "Rejected" && (
          <button className="rounded-xl border border-red-300 text-red-700 px-3 py-1 text-sm" onClick={() => onReject?.(task)}>
            Reject
          </button>
        )}
      </div>
    </div>
  );
}
