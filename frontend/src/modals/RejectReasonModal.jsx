import { useState } from "react";

export default function RejectReasonModal({ task, onClose, onSaved }) {
  const [value, setValue] = useState(task?.body || "");

  async function reject() {
    await fetch(`/api/tasks/${task.id}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "reject", reason: value }),
    });
    onSaved?.();
  }

  return (
    <div className="p-4">
      <h4 className="text-base font-semibold">Reject Reason</h4>
      <textarea
        className="mt-2 w-full rounded-lg border p-2"
        rows={4}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Write the reason…"
      />
      <div className="mt-3 flex justify-end gap-2">
        <button className="rounded-xl border px-3 py-1 text-sm" onClick={onClose}>Cancel</button>
        <button className="rounded-xl bg-red-600 text-white px-3 py-1 text-sm" onClick={reject} disabled={!value.trim()}>
          Reject
        </button>
      </div>
    </div>
  );
}
