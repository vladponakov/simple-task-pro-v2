import { useState } from "react";

export default function EditReasonModal({ task, onClose, onSaved }) {
  const [value, setValue] = useState(task?.body || "");

  async function save() {
    await fetch(`/api/tasks/${task.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: value }), // 'reason' also works; server maps to 'body'
    });
    onSaved?.();
  }

  return (
    <div className="p-4">
      <h4 className="text-base font-semibold">Edit Reason</h4>
      <textarea
        className="mt-2 w-full rounded-lg border p-2"
        rows={4}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Write the reason…"
      />
      <div className="mt-3 flex justify-end gap-2">
        <button className="rounded-xl border px-3 py-1 text-sm" onClick={onClose}>Cancel</button>
        <button className="rounded-xl bg-blue-600 text-white px-3 py-1 text-sm" onClick={save}>
          Save
        </button>
      </div>
    </div>
  );
}
