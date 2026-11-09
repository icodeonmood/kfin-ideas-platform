"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { recordText, SHOWCASE_LABELS } from "@/components/showcase-view";
import type { ShowcaseBrief } from "@/server/ones";

const ERRORS: Record<string, string> = {
  personal_data: "Please take out any personal details (numbers, addresses, investor names) and try again.",
  text_needs_review: "Please reword this: it reads as off-topic or unkind, so we can't save it as it is.",
  names_not_allowed: "Leave out the names of colleagues and clients: everyone will see this.",
  text_too_long: "Please keep each part under 600 characters.",
  checks_unavailable: "We can't check text just now. Please try again in a few minutes.",
};

export function ShowcaseForm({ brief }: { brief: ShowcaseBrief }) {
  const router = useRouter();
  const base = useId();
  const [parts, setParts] = useState<Record<string, string>>(
    Object.fromEntries(brief.parts.map((p) => [p.key, p.own])),
  );
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  return (
    <form
      className="stack-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setError("");
        const res = await fetch("/api/me/one/showcase", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(parts),
        }).catch(() => null);
        if (res?.ok) {
          setStatus("Saved. The committee sees your latest version.");
          router.refresh();
          return;
        }
        const code = res
          ? String(((await res.json().catch(() => ({}))) as { error?: string }).error ?? "")
          : "";
        setError(ERRORS[code] ?? "That didn't save. Please try again.");
      }}
    >
      <p role="status" aria-live="polite" className="sr-status">
        {status}
      </p>
      {error ? (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      ) : null}
      {brief.parts.map((p) => {
        const id = `${base}-${p.key}`;
        const record = recordText(brief, p.key, p.from_record);
        return (
          <div key={p.key}>
            <label htmlFor={id}>{SHOWCASE_LABELS[p.key]?.title}</label>
            <p className="hint" id={`${id}-hint`}>
              {SHOWCASE_LABELS[p.key]?.ask}
              {record ? ` Your record says: ${record}` : ""}
            </p>
            <textarea
              id={id}
              rows={3}
              maxLength={600}
              value={parts[p.key] ?? ""}
              aria-describedby={`${id}-hint`}
              onChange={(e) => setParts((x) => ({ ...x, [p.key]: e.target.value }))}
            />
          </div>
        );
      })}
      <div className="actions">
        <button type="submit" className="button">
          Save your brief
        </button>
      </div>
    </form>
  );
}
