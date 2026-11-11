"use client";

/**
 * Section 6 file upload (§4.2 attachments, AT-B3-06/07). Every file goes to quarantine and is checked before
 * anyone can open it. The list shows plain-words state and polls while checks run.
 */
import { useEffect, useRef, useState } from "react";

export type AttachmentState = "quarantine" | "processing" | "awaiting_check" | "clean" | "rejected";
export type AttachmentItem = {
  id: string;
  name: string;
  bytes: number;
  state: AttachmentState;
  rejection: { type: string; code?: string; location: string } | null;
};
export type AttachmentLimits = {
  max_files: number;
  max_mb_each: number;
  max_mb_per_idea: number;
  allowed: string[];
};

const TYPE_NAMES: Record<string, string> = {
  pdf: "PDF",
  docx: "Word",
  pptx: "PowerPoint",
  xlsx: "Excel",
  csv: "CSV",
  png: "PNG",
  jpg: "JPG",
};
const ACCEPT: Record<string, string> = {
  pdf: ".pdf,application/pdf",
  docx: ".docx",
  pptx: ".pptx",
  xlsx: ".xlsx",
  csv: ".csv,text/csv",
  png: ".png,image/png",
  jpg: ".jpg,.jpeg,image/jpeg",
};
const POLL_MS = 2000;

function size(bytes: number) {
  return bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function stateText(a: AttachmentItem): string {
  switch (a.state) {
    case "quarantine":
    case "processing":
      return "Checking this file…";
    case "awaiting_check":
      return "Kept aside for a closer check. Nobody can open it until that check is done.";
    case "clean":
      return "Checked. Ready for the committee.";
    case "rejected": {
      const code = a.rejection?.code;
      if (code === "too_big")
        return "Not accepted: this file is too big for us to check fully. It has been deleted. Attach a smaller extract.";
      if (code === "check_failed")
        return "We couldn't finish checking this file, so it has been deleted. Please attach it again later.";
      if (code === "virus") return "Not accepted: our virus check flagged this file. It has been deleted.";
      if (code === "gatekeeper")
        return `Not accepted: our check found what looks like details of an investor, customer or other person (${a.rejection?.location ?? "somewhere in the file"}). It has been deleted. Remove those details and attach the file again.`;
      if (code === "unreadable")
        return "Not accepted: we couldn't open this file to check it. It has been deleted. Try saving it again or as a PDF.";
      const what =
        code === "column" ? "personal details in a column" : `a ${a.rejection?.type ?? "personal detail"}`;
      return `Not accepted: this file has what looks like ${what} (${a.rejection?.location ?? "somewhere in the file"}). It has been deleted. Remove those details and attach the file again.`;
    }
  }
}

function uploadError(code: string, limits: AttachmentLimits, kinds: string): string {
  switch (code) {
    case "file_too_large":
      return `This file is bigger than ${limits.max_mb_each} MB. Try a smaller copy.`;
    case "type_not_allowed":
      return `We can't take this type of file. Use ${kinds}.`;
    case "too_many_files":
      return `You can attach up to ${limits.max_files} files. Remove one to add another.`;
    case "idea_total_too_large":
      return `Files on one idea can add up to ${limits.max_mb_per_idea} MB. Remove one to add another.`;
    case "file_empty":
      return "This file is empty.";
    case "name_has_personal_data":
      return "The file name looks like it has personal details or a colleague's or client's name. Rename the file and attach it again.";
    default:
      return "We couldn't attach this file just now. Please try again.";
  }
}

export function Attachments(p: {
  ideaId: string;
  files: AttachmentItem[];
  onChange: (next: AttachmentItem[] | ((prev: AttachmentItem[]) => AttachmentItem[])) => void;
  limits: AttachmentLimits;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const kinds = p.limits.allowed.map((k) => TYPE_NAMES[k] ?? k.toUpperCase()).join(", ");
  const { onChange, files } = p;
  const pending = files.filter((f) => f.state === "quarantine" || f.state === "processing").map((f) => f.id);
  const pendingKey = pending.join(",");

  // Poll the files still being checked.
  useEffect(() => {
    if (!pendingKey) return;
    const timer = setInterval(async () => {
      const updates = await Promise.all(
        pendingKey.split(",").map(async (id) => {
          const res = await fetch(`/api/attachments/${id}/status`).catch(() => null);
          return res?.ok ? ((await res.json()) as AttachmentItem) : null;
        }),
      );
      onChange((prev) =>
        prev.map((f) => {
          const u = updates.find((x) => x?.id === f.id);
          return u ? { ...f, state: u.state, rejection: u.rejection } : f;
        }),
      );
      // Say each finished check out loud through the status line (the list itself is not a live region).
      const finished = updates.filter(
        (u): u is AttachmentItem => !!u && u.state !== "quarantine" && u.state !== "processing",
      );
      if (finished.length) {
        setMessage({
          text: finished.map((u) => `${u.name}: ${stateText(u)}`).join(" "),
          error: finished.some((u) => u.state === "rejected"),
        });
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [pendingKey, onChange]);

  async function attach(file: File) {
    if (busy) return;
    setMessage(null);
    if (file.size > p.limits.max_mb_each * 1024 * 1024) {
      setMessage({ text: uploadError("file_too_large", p.limits, kinds), error: true });
      return;
    }
    setBusy(true);
    const form = new FormData();
    form.set("file", file);
    const res = await fetch(`/api/submissions/${p.ideaId}/attachments`, { method: "POST", body: form }).catch(
      () => null,
    );
    const body = (await res?.json().catch(() => null)) as (AttachmentItem & { error?: string }) | null;
    setBusy(false);
    if (input.current) input.current.value = "";
    if (res?.status !== 201 || !body) {
      setMessage({ text: uploadError(body?.error ?? "", p.limits, kinds), error: true });
      return;
    }
    onChange((prev) => [
      ...prev,
      { id: body.id, name: body.name, bytes: body.bytes, state: body.state, rejection: null },
    ]);
    setMessage({ text: `${body.name} is attached. We're checking it now.`, error: false });
  }

  async function removeFile(a: AttachmentItem) {
    const res = await fetch(`/api/submissions/${p.ideaId}/attachments/${a.id}`, { method: "DELETE" }).catch(
      () => null,
    );
    if (res?.status === 204) {
      onChange((prev) => prev.filter((f) => f.id !== a.id));
      setMessage({ text: `${a.name} is removed.`, error: false });
      input.current?.focus(); // the button that had focus is gone
      return;
    } else {
      setMessage({ text: "We couldn't remove that file just now. Please try again.", error: true });
    }
  }

  const full = files.filter((f) => f.state !== "rejected").length >= p.limits.max_files;
  return (
    <div className="field attachments">
      <label htmlFor="f-attachments">Attach a file (optional)</label>
      <p id="f-attachments-hint" className="hint">
        {kinds}. Up to {p.limits.max_files} files, {p.limits.max_mb_each} MB each. We check every file for
        viruses and personal details before anyone can open it. Do not attach files with investor or customer
        details.
      </p>
      <input
        ref={input}
        id="f-attachments"
        type="file"
        accept={p.limits.allowed.map((k) => ACCEPT[k] ?? "").join(",")}
        aria-describedby="f-attachments-hint"
        aria-disabled={busy || full ? true : undefined}
        onClick={(e) => {
          // Not `disabled`: that would drop keyboard focus while a file uploads.
          if (busy || full) {
            e.preventDefault();
            setMessage({
              text: full
                ? uploadError("too_many_files", p.limits, kinds)
                : "Please wait until this file is attached.",
              error: full,
            });
          }
        }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void attach(file);
        }}
      />
      <p className={message?.error ? "field-error" : "muted"} role="status" aria-live="polite">
        {busy ? "Attaching…" : (message?.text ?? "")}
      </p>
      {files.length ? (
        <ul className="attachment-list" aria-label="Attached files">
          {files.map((a) => (
            <li key={a.id} className={`attachment attachment-${a.state}`}>
              <span className="attachment-name">
                {a.name} <span className="muted">({size(a.bytes)})</span>
              </span>
              <span className="attachment-state">{stateText(a)}</span>
              <button type="button" className="btn btn-quiet" onClick={() => void removeFile(a)}>
                Remove<span className="visually-hidden"> {a.name}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
