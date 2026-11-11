"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Status } from "@/components/status";

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
        <Status kind="error" title={<>We couldn&apos;t start that just now. Please try again.</>} />
      ) : null}
      <ul className="share-ways" aria-label="Two ways in">
        <li className="glass share-way share-way-quick" data-lit="" data-edge="">
          <span className="share-way-slash" aria-hidden="true">
            <i className="slash" />
          </span>
          <h2>Quick capture</h2>
          <p>
            About a minute. One box: say it your way, in any language, and add files if you have them. The
            assistant suggests the rest for you to check.
          </p>
          <button
            type="button"
            className="btn btn-primary btn-lg"
            onClick={() => start("quick")}
            disabled={busy !== null}
            aria-busy={busy === "quick" ? "true" : undefined}
          >
            {busy === "quick" ? "Starting…" : "Start a quick capture"}
          </button>
        </li>
        <li className="glass share-way" data-lit="">
          <h2>Full canvas</h2>
          <p>Five to ten minutes. Six short sections that make your idea stronger for the committee.</p>
          <button
            type="button"
            className="btn btn-secondary btn-lg"
            onClick={() => start("full")}
            disabled={busy !== null}
            aria-busy={busy === "full" ? "true" : undefined}
          >
            {busy === "full" ? "Starting…" : "Start the full canvas"}
          </button>
        </li>
      </ul>
    </>
  );
}
