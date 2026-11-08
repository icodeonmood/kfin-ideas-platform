"use client";

import { useState } from "react";

export function AcceptNotice({ version, next }: { version: string; next: string }) {
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");
  async function accept() {
    setState("saving");
    const res = await fetch("/api/me/privacy-notice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version }),
    });
    if (res.ok) window.location.assign(next);
    else setState("error");
  }
  return (
    <>
      {state === "error" ? (
        <p role="alert" className="notice notice-error">
          We couldn&apos;t save that. Please reload the page and try again.
        </p>
      ) : null}
      <button type="button" className="button" onClick={accept} disabled={state === "saving"}>
        {state === "saving" ? "Saving…" : "I have read this — continue"}
      </button>
    </>
  );
}
