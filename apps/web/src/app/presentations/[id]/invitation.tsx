"use client";

/** A contributor accepts the invitation: up to three presenters from the group and a slot; then edits the outline. */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

export type ContributorPresentation = {
  id: string;
  cluster_id: string;
  name: string | null;
  state: string;
  reply_due: string | null;
  slot_options: string[];
  slot_at: string | null;
  presenters: string[];
  my_codes: string[];
  contributors: string[];
  outline: { slides: { title: string; points: string[] }[] } | null;
};

const when = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });

const ERRORS: Record<string, string> = {
  presenters_from_the_cluster_1_to_3: "Please choose one to three presenters from the group.",
  slot_from_the_options: "Please choose one of the times offered.",
  one_to_eight_slides: "The outline has one to eight slides.",
  personal_data: "Please take out personal details first.",
  not_open: "This invitation is no longer open.",
};

export function Invitation({ id, view }: { id: string; view: ContributorPresentation }) {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [presenters, setPresenters] = useState<string[]>(
    view.presenters.length ? view.presenters : view.my_codes.slice(0, 1),
  );
  const [slot, setSlot] = useState(view.slot_options[0] ?? "");
  const [slides, setSlides] = useState(view.outline?.slides ?? []);

  async function send(body: Record<string, unknown>, done: string) {
    setBusy(true);
    const res = await fetch(`/api/presentations/${id}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { error?: string } | null;
    setBusy(false);
    setMessage(
      res?.ok
        ? { text: done, error: false }
        : { text: ERRORS[String(out?.error)] ?? "That did not go through. Please try again.", error: true },
    );
    statusRef.current?.focus();
    if (res?.ok) router.refresh();
  }

  return (
    <>
      <p
        ref={statusRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className={message?.error ? "field-error" : "muted"}
      >
        {message?.text ?? ""}
      </p>
      {view.state === "invited" ? (
        <section aria-labelledby="i-accept" className="panel">
          <h2 id="i-accept">Accept{view.reply_due ? ` by ${when(view.reply_due)}` : ""}</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send({ action: "accept", presenters, slot }, "Accepted. The committee is told.");
            }}
          >
            <fieldset>
              <legend>Who presents (up to three, by contributor code)</legend>
              {view.contributors.map((c) => (
                <label key={c}>
                  <input
                    type="checkbox"
                    checked={presenters.includes(c)}
                    onChange={(e) =>
                      setPresenters(e.target.checked ? [...presenters, c] : presenters.filter((p) => p !== c))
                    }
                  />{" "}
                  {c}
                  {view.my_codes.includes(c) ? " (you)" : ""}
                </label>
              ))}
            </fieldset>
            <fieldset>
              <legend>When</legend>
              {view.slot_options.map((s) => (
                <label key={s}>
                  <input type="radio" name="i-slot" checked={slot === s} onChange={() => setSlot(s)} />{" "}
                  {when(s)}
                </label>
              ))}
            </fieldset>
            <button type="submit" className="button" disabled={busy}>
              Accept the invitation
            </button>
          </form>
        </section>
      ) : (
        <p>{view.slot_at ? `You present on ${when(view.slot_at)}.` : `This invitation is ${view.state}.`}</p>
      )}
      {slides.length && ["invited", "scheduled"].includes(view.state) ? (
        <section aria-labelledby="i-outline" className="panel">
          <h2 id="i-outline">Your outline (a starting point; it is yours to change)</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send({ action: "save_outline", slides }, "Outline saved.");
            }}
          >
            {slides.map((s, i) => (
              <div className="field" key={i}>
                <label htmlFor={`o-${i}`}>
                  Slide {i + 1}: {s.title}
                </label>
                <textarea
                  id={`o-${i}`}
                  rows={3}
                  value={s.points.join("\n")}
                  onChange={(e) =>
                    setSlides(
                      slides.map((x, j) => (j === i ? { ...x, points: e.target.value.split("\n") } : x)),
                    )
                  }
                />
              </div>
            ))}
            <button type="submit" className="button button-secondary" disabled={busy}>
              Save the outline
            </button>
          </form>
        </section>
      ) : null}
    </>
  );
}
