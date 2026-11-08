"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/** Start a quick capture or a full canvas: creates a draft, then opens it. */
export function StartButtons() {
  const router = useRouter();
  const [busy, setBusy] = useState<"quick" | "full" | null>(null);
  const [failed, setFailed] = useState(false);

  async function start(mode: "quick" | "full") {
    setBusy(mode);
    const res = await fetch("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    if (!res.ok) {
      setFailed(true);
      setBusy(null);
      return;
    }
    router.push(`/share/${((await res.json()) as { id: string }).id}`);
  }

  return (
    <>
      {failed ? (
        <p role="alert" className="notice notice-error">
          We couldn&apos;t start that just now. Please try again.
        </p>
      ) : null}
      <ul className="cards" aria-label="Two ways in">
        <li className="card">
          <h2>Quick capture</h2>
          <p>About a minute. Three questions; the assistant drafts the rest for you to check later.</p>
          <button type="button" className="button" onClick={() => start("quick")} disabled={busy !== null}>
            {busy === "quick" ? "Starting…" : "Start a quick capture"}
          </button>
        </li>
        <li className="card">
          <h2>Full canvas</h2>
          <p>Five to ten minutes. Six short sections that make your idea stronger for the committee.</p>
          <button type="button" className="button" onClick={() => start("full")} disabled={busy !== null}>
            {busy === "full" ? "Starting…" : "Start the full canvas"}
          </button>
        </li>
      </ul>
    </>
  );
}
