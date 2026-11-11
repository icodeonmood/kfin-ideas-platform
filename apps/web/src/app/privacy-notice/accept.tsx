"use client";

import { useState } from "react";

import { Status } from "@/components/status";

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
        <Status kind="error" title={<>We couldn&apos;t save that. Please reload the page and try again.</>} />
      ) : null}
      <button
        type="button"
        className="btn btn-primary btn-lg notice-accept"
        onClick={accept}
        disabled={state === "saving"}
        aria-busy={state === "saving" ? "true" : undefined}
      >
        {state === "saving" ? "Saving…" : "I have read this — continue"}
      </button>
    </>
  );
}
