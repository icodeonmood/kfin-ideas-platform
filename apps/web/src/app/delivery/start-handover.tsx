"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { ERRORS, Err } from "./actions";

const TRACKS = [
  ["build", "Build"],
  ["fix", "Non-tech fix"],
  ["procurement", "Buy or partner"],
] as const;

/** A committee member or an admin opens the handover for a picked idea or group (§4.8 step 1). */
export function StartHandover({ subjectType, subjectId }: { subjectType: string; subjectId: string }) {
  const router = useRouter();
  const [track, setTrack] = useState("build");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const trackId = useId();
  async function start() {
    if (busy) return;
    setBusy(true);
    const res = await fetch("/api/delivery", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_type: subjectType, subject_id: subjectId, track }),
    }).catch(() => null);
    const out = res ? ((await res.json().catch(() => ({}))) as { id?: number; error?: string }) : {};
    setBusy(false);
    if (res?.ok && out.id) {
      router.push(`/delivery/${out.id}`);
      return;
    }
    setError(ERRORS[String(out.error ?? "")] ?? "That didn't work. Please try again.");
  }
  return (
    <div className="inline-form">
      <label htmlFor={trackId}>Track</label>
      <select id={trackId} value={track} onChange={(e) => setTrack(e.target.value)}>
        {TRACKS.map(([value, words]) => (
          <option key={value} value={value}>
            {words}
          </option>
        ))}
      </select>
      <button type="button" className="button" disabled={busy} onClick={() => void start()}>
        Start the handover
      </button>
      <Err text={error} />
    </div>
  );
}
