"use client";

import { useEffect, useRef, useState } from "react";

import { ChoiceChips } from "@/components/ui/chips";
import { FieldMsg } from "@/components/ui/field";

import {
  isReferAs,
  REFER_AS_LINE,
  REFER_AS_OPTIONS,
  REFER_AS_TITLE,
  SAVE_FAILED,
  type ReferAs,
} from "./rules";

/**
 * "How should we refer to you?" (DEC-108 (3), BLD-E010, BLD-E043). Lane C owns the answer and its store through
 * `GET/PUT /api/me/refer-as` ({ refer_as: "she" | "he" | "they" | "unset" }, 400 `refer_as_invalid`); this screen
 * only calls that contract, typed here, and imports nothing of lane C's. The question shows once the route answers:
 * until it is on the server it stays out of the way. A choice saves at once, as the switches do; a failed save goes
 * back to the last saved answer with "Couldn't save that. Try again." under the choices (V-FIELDS.one/5).
 */
export function ReferAsCard() {
  const [saved, setSaved] = useState<ReferAs | null>(null);
  const [shown, setShown] = useState<ReferAs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    const ask = new AbortController();
    fetch("/api/me/refer-as", { signal: ask.signal, cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<{ refer_as?: unknown }>) : null))
      .then((body) => {
        if (body && isReferAs(body.refer_as)) {
          setSaved(body.refer_as);
          setShown(body.refer_as);
        }
      })
      .catch(() => undefined);
    return () => ask.abort();
  }, []);

  if (shown === null || saved === null) return null;

  const choose = async (value: string) => {
    if (!isReferAs(value)) return;
    const mine = ++seq.current;
    setShown(value);
    setError(null);
    const res = await fetch("/api/me/refer-as", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refer_as: value }),
    }).catch(() => null);
    const body = (await res?.json().catch(() => null)) as { refer_as?: unknown } | null;
    if (mine !== seq.current) return; // a later choice is on its way; its answer decides
    if (res?.ok && isReferAs(body?.refer_as)) {
      setSaved(body.refer_as);
      setShown(body.refer_as);
      return;
    }
    setShown(saved);
    setError(SAVE_FAILED);
  };

  return (
    <section className="pf-card" aria-labelledby="pf-ref-h">
      <h2 id="pf-ref-h" className="pf-k">
        {REFER_AS_TITLE}
      </h2>
      <p className="pf-d pf-ref-d">{REFER_AS_LINE}</p>
      <div className="pf-ref">
        <ChoiceChips
          label={REFER_AS_TITLE}
          options={REFER_AS_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
          value={shown}
          onChange={(v) => void choose(v)}
        />
      </div>
      {error ? <FieldMsg>{error}</FieldMsg> : null}
    </section>
  );
}
