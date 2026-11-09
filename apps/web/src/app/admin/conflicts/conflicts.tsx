"use client";

/** Clear a manager's conflict flag with a reason (§3.1). Every clearing is in the audit log. */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

export type Flag = {
  round_id: string;
  cluster_id: string;
  member_id: string;
  name: string;
  flagged_at: string;
};

const ERRORS: Record<string, string> = {
  reason_required: "Please give a reason of at least 10 characters.",
  reason_too_short: "Please give a reason of at least 10 characters.",
  personal_data: "Please leave out personal details such as PAN or phone numbers.",
  no_flag_to_clear: "This flag is already cleared or the member stepped aside.",
  contributors_recuse: "This colleague has an idea in the group, so they step aside.",
  admin_only: "Only an admin can clear a flag.",
};

export function Conflicts({ initial }: { initial: Flag[] }) {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const key = (f: Flag) => `${f.round_id}:${f.member_id}`;

  async function clear(f: Flag) {
    setBusy(true);
    setMessage(null);
    const res = await fetch("/api/admin/conflicts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ round_id: f.round_id, member_id: f.member_id, reason: reasons[key(f)] ?? "" }),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { error?: string } | null;
    setBusy(false);
    setMessage(
      res?.ok
        ? { text: `Cleared. ${f.name} can now score ${f.cluster_id}.`, error: false }
        : { text: ERRORS[String(out?.error)] ?? "That did not go through. Please try again.", error: true },
    );
    statusRef.current?.focus();
    if (res?.ok) router.refresh();
  }

  return (
    <section aria-labelledby="c-list" className="panel">
      <h2 id="c-list">Waiting for an admin</h2>
      <p
        ref={statusRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className={message?.error ? "field-error" : "muted"}
      >
        {message?.text ?? ""}
      </p>
      {initial.length === 0 ? (
        <p>No flags are waiting.</p>
      ) : (
        <ul>
          {initial.map((f) => (
            <li key={key(f)}>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void clear(f);
                }}
              >
                <p>
                  <strong>{f.name}</strong> on review {f.round_id} of {f.cluster_id}, flagged{" "}
                  {new Date(f.flagged_at).toLocaleDateString("en-IN", {
                    dateStyle: "medium",
                    timeZone: "Asia/Kolkata",
                  })}
                  .
                </p>
                <div className="field">
                  <label htmlFor={`c-${key(f)}`}>Why it is fine for {f.name} to score this group</label>
                  <textarea
                    id={`c-${key(f)}`}
                    rows={2}
                    maxLength={1000}
                    value={reasons[key(f)] ?? ""}
                    onChange={(e) => setReasons({ ...reasons, [key(f)]: e.target.value })}
                  />
                </div>
                <button type="submit" className="button button-secondary" disabled={busy}>
                  Clear the flag
                </button>
              </form>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
