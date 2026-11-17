"use client";

import { useRef, useState } from "react";

import { ChoiceChips } from "@/components/ui/chips";
import { FieldMsg } from "@/components/ui/field";
import { parseReferAs, type ReferAs } from "@/lib/refer-as";

import { REFER_AS_LINE, REFER_AS_OPTIONS, REFER_AS_TITLE, SAVE_FAILED } from "./rules";

/**
 * "How should we refer to you?" (DEC-108 (3), BLD-E010, BLD-E043). Lane C owns the answer and its store (BLD-C111):
 * the page reads it on the server through `server/refer-as.ts`, and a choice saves at once through
 * `PUT /api/me/refer-as`, as the switches do. A save that does not land (400 `refer_as_invalid`, or anything else)
 * goes back to the last saved answer with "Couldn't save that. Try again." under the choices (V-FIELDS.one/5).
 * `initial` is null when the answer could not be read; nothing is chosen then, and a choice still saves.
 */
export function ReferAsCard({ initial }: { initial: ReferAs | null }) {
  const [saved, setSaved] = useState<ReferAs | null>(initial);
  const [shown, setShown] = useState<ReferAs | null>(initial);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  const choose = async (value: string) => {
    const next = typeof value === "string" ? parseReferAs(value) : undefined;
    if (!next) return;
    const mine = ++seq.current;
    setShown(next);
    setError(null);
    const res = await fetch("/api/me/refer-as", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refer_as: next }),
    }).catch(() => null);
    const body = (await res?.json().catch(() => null)) as { refer_as?: unknown } | null;
    if (mine !== seq.current) return; // a later choice is on its way; its answer decides
    const landed = res?.ok && typeof body?.refer_as === "string" ? parseReferAs(body.refer_as) : undefined;
    if (landed) {
      setSaved(landed);
      setShown(landed);
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
