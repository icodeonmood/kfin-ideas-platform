"use client";

/** Review desk actions (§4.3): decide (accept or edit, with a note for category or play), redirect, ask a
 * question, change visibility, hold as spam or abuse (a second reviewer confirms). */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

export type ItemView = {
  mode: "real" | "neutral";
  item: {
    id: number;
    type: string;
    state: string;
    assigned_to: string | null;
    final: Record<string, unknown> | null;
    timer: { stage: string; state: string; due_at: string } | null;
    vetoed: boolean;
    veto_reason: string | null;
  };
  idea: {
    id: string;
    stage: string;
    strength: number | null;
    visibility: string;
    card: Record<string, unknown> & { details?: string };
    original_text: string | null;
    provenance: Record<string, string>;
    attachments: { id: string; name: string; state: string }[];
  };
  proposals: {
    system: {
      areas?: string[];
      lobs?: string[];
      systems?: string[];
      roles_affected?: string[];
      scope?: string | null;
    };
    confidence: Record<string, number>;
    flags: string[];
    contested: "investor_or_customer" | "personal_data" | null;
    person_says: string | null;
    best_same: string | null;
    suggested_action: string | null;
  };
  candidates: {
    cid: string;
    type: string;
    label: string;
    reason: string | null;
    summary: string | null;
    visibility: string;
  }[];
  history: { event: string; by: string; at: string }[];
  taxonomy: { areas: { id: string; name: string }[]; lobs: { id: string; name: string }[] };
};

const ERRORS: Record<string, string> = {
  text_too_short: "Please add a note of at least 10 characters. It goes to the person.",
  personal_data: "Please take out personal details first.",
  already_decided: "This item has already been decided.",
  assigned_to_someone_else: "This item is with someone else now.",
  second_reviewer_needed: "A different reviewer has to confirm this hold.",
  canvas_not_strong: "Only a canvas at strength 4 or more can be confirmed as strong.",
  cluster_not_found: "That cluster does not exist.",
  idea_not_found: "That idea does not exist.",
  not_ready_for_review: "This idea is not ready for a decision yet.",
  awaiting_hold_confirmation: "A hold is waiting for a second reviewer. Nothing else can change until then.",
  no_hold_to_confirm: "There is no hold waiting to be confirmed.",
  own_idea: "You cannot act on an idea you shared or are linked to. Another reviewer will take it.",
  visibility_required: "Please choose who can see it, and give a reason.",
  redirect_kind_required: "Please choose where it should go.",
  hold_kind_required: "Please choose spam or abuse.",
  unknown_areas: "One of the area tags is not in the list. Please refresh and try again.",
  unknown_lobs: "One of the LOBs is not in the list. Please refresh and try again.",
  unknown_systems: "One of the systems is not in the list. Please refresh and try again.",
  unknown_roles_affected: "One of the roles is not in the list. Please refresh and try again.",
  bad_category: "Please choose a category from the list.",
  bad_play: "Please choose a play from the list.",
  bad_scope: "Please choose a scope from the list.",
  bad_request: "Something in the form was not right. Please refresh and try again.",
};

function toggle(list: string[], id: string, on: boolean) {
  return on ? [...new Set([...list, id])] : list.filter((x) => x !== id);
}

export function Actions({ id, view, me }: { id: string; view: ItemView; me: string }) {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const sys = view.proposals.system;
  const value = (view.idea.card.value ?? {}) as { category?: string; play?: string | null };
  const [areas, setAreas] = useState<string[]>(sys.areas ?? []);
  const [lobs, setLobs] = useState<string[]>(sys.lobs ?? []);
  const [scope, setScope] = useState(sys.scope ?? "lob");
  const [category, setCategory] = useState(value.category ?? "not_sure");
  const [play, setPlay] = useState(value.play ?? "");
  const [note, setNote] = useState("");
  const [attach, setAttach] = useState<"new" | "cluster" | "idea">("new");
  const [attachId, setAttachId] = useState("");
  const [strong, setStrong] = useState(false);
  const [question, setQuestion] = useState("");
  const [redirectKind, setRedirectKind] = useState("it_ticket");
  const [visibility, setVisibility] = useState(view.idea.visibility);
  const [visReason, setVisReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const changed = category !== (value.category ?? "not_sure") || play !== (value.play ?? "");
  const open = ["open", "in_progress", "awaiting_second_reviewer"].includes(view.item.state);
  const mine = !view.item.assigned_to || view.item.assigned_to === me;
  const holding = view.item.state === "awaiting_second_reviewer";
  const holdBy = String(view.item.final?.requested_by ?? "");
  const [pendingHold, setPendingHold] = useState<"spam" | "abuse" | null>(null);

  async function send(body: Record<string, unknown>, done: string) {
    setBusy(true);
    setMessage(null);
    const res = await fetch(`/api/review/items/${id}/action`, {
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

  if (holding)
    return (
      <section aria-labelledby="p-actions" className="panel">
        <h2 id="p-actions">Actions</h2>
        <p
          ref={statusRef}
          tabIndex={-1}
          role="status"
          aria-live="polite"
          className={message?.error ? "field-error" : "muted"}
        >
          {message?.text ?? ""}
        </p>
        <div className="notice">
          <p>
            A reviewer has asked to hold this as {String(view.item.final?.hold ?? "spam")}. A second reviewer
            confirms. Nothing else can change until then.
          </p>
          {holdBy === me ? (
            <p>You asked for this hold, so a different reviewer has to confirm it.</p>
          ) : (
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => void send({ action: "confirm_hold" }, "Hold confirmed.")}
            >
              Confirm the hold
            </button>
          )}
        </div>
      </section>
    );

  if (!open || !mine)
    return (
      <section aria-labelledby="p-actions" className="panel">
        <h2 id="p-actions">Actions</h2>
        <p
          ref={statusRef}
          tabIndex={-1}
          role="status"
          aria-live="polite"
          className={message?.error ? "field-error" : "muted"}
        >
          {message?.text ?? ""}
        </p>
        <p>{!open ? "This item has been decided." : "This item is with another member of the committee."}</p>
      </section>
    );

  return (
    <section aria-labelledby="p-actions" className="panel">
      <h2 id="p-actions">Actions</h2>
      <p
        ref={statusRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className={message?.error ? "field-error" : "muted"}
      >
        {message?.text ?? ""}
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send(
            {
              action: "decide",
              system: {
                areas,
                lobs,
                scope,
                systems: sys.systems ?? [],
                roles_affected: sys.roles_affected ?? [],
              },
              ...(changed ? { category, play: play || null, note } : {}),
              attach: attach === "new" ? { type: "new" } : { type: attach, id: attachId.trim() },
              strong_canvas: strong,
            },
            "Decision saved. The person will hear from us.",
          );
        }}
      >
        <h3>Decide</h3>
        <fieldset className="field">
          <legend>Area tags</legend>
          {view.taxonomy.areas.map((a) => (
            <label key={a.id} className="choice">
              <input
                type="checkbox"
                checked={areas.includes(a.id)}
                onChange={(e) => setAreas((x) => toggle(x, a.id, e.target.checked))}
              />
              {a.name}
            </label>
          ))}
        </fieldset>
        <fieldset className="field">
          <legend>LOBs</legend>
          {view.taxonomy.lobs.map((a) => (
            <label key={a.id} className="choice">
              <input
                type="checkbox"
                checked={lobs.includes(a.id)}
                onChange={(e) => setLobs((x) => toggle(x, a.id, e.target.checked))}
              />
              {a.name}
            </label>
          ))}
        </fieldset>
        <fieldset className="field">
          <legend>Scope</legend>
          {[
            ["lob", "One LOB"],
            ["cross-lob", "Several LOBs"],
            ["org-wide", "Whole company"],
          ].map(([v, l]) => (
            <label key={v} className="choice">
              <input type="radio" name="scope" checked={scope === v} onChange={() => setScope(v!)} />
              {l}
            </label>
          ))}
        </fieldset>
        <div className="field">
          <label htmlFor="d-category">Category (the person&apos;s answer)</label>
          <select id="d-category" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="cost_saving">Cost saving</option>
            <option value="new_revenue">New revenue</option>
            <option value="both">Both</option>
            <option value="not_sure">Not sure</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="d-play">Play</label>
          <select id="d-play" value={play} onChange={(e) => setPlay(e.target.value)}>
            <option value="">Not set</option>
            <option value="process_improvement">Process improvement</option>
            <option value="upsell">Upsell</option>
            <option value="cross_sell">Cross-sell</option>
            <option value="new_product">New product</option>
            <option value="other">Other</option>
          </select>
        </div>
        {changed ? (
          <div className="field">
            <label htmlFor="d-note">Why you changed their answer (they will see this)</label>
            <textarea id="d-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
        ) : null}
        <fieldset className="field">
          <legend>Group with</legend>
          {[
            ["new", "Keep it on its own"],
            ["cluster", "Attach to a cluster"],
            ["idea", "Attach to an idea"],
          ].map(([v, l]) => (
            <label key={v} className="choice">
              <input
                type="radio"
                name="attach"
                checked={attach === v}
                onChange={() => setAttach(v as typeof attach)}
              />
              {l}
            </label>
          ))}
          {attach !== "new" ? (
            <div className="field">
              <label htmlFor="d-attach-id">
                {attach === "cluster" ? "Cluster ID (CL-…)" : "Idea ID (IDEA-…)"}
              </label>
              <input id="d-attach-id" value={attachId} onChange={(e) => setAttachId(e.target.value)} />
            </div>
          ) : null}
        </fieldset>
        <label className="choice">
          <input
            type="checkbox"
            checked={strong}
            disabled={(view.idea.strength ?? 0) < 4}
            onChange={(e) => setStrong(e.target.checked)}
          />
          Confirm a strong canvas (strength 4 or more earns points)
        </label>
        <div className="button-row">
          <button type="submit" className="button" disabled={busy}>
            Save decision
          </button>
        </div>
      </form>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send(
            { action: "ask", question },
            "Question sent. The review clock is paused until they answer.",
          );
        }}
      >
        <h3>Ask the person a question</h3>
        <div className="field">
          <label htmlFor="d-question">Your question</label>
          <textarea id="d-question" rows={3} value={question} onChange={(e) => setQuestion(e.target.value)} />
        </div>
        <button type="submit" className="button button-secondary" disabled={busy}>
          Send the question
        </button>
      </form>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send({ action: "redirect", kind: redirectKind }, "Redirected. The person has the details.");
        }}
      >
        <h3>Redirect</h3>
        <div className="field">
          <label htmlFor="d-redirect">Where it should go</label>
          <select id="d-redirect" value={redirectKind} onChange={(e) => setRedirectKind(e.target.value)}>
            <option value="it_ticket">IT helpdesk</option>
            <option value="hr_grievance">HR</option>
            <option value="complaint">Admin and facilities</option>
            <option value="question">Intranet help</option>
          </select>
        </div>
        <button type="submit" className="button button-secondary" disabled={busy}>
          Redirect
        </button>
      </form>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send({ action: "visibility", visibility, reason: visReason }, "Visibility changed.");
        }}
      >
        <h3>Visibility</h3>
        <div className="field">
          <label htmlFor="d-vis">Who can see it</label>
          <select id="d-vis" value={visibility} onChange={(e) => setVisibility(e.target.value)}>
            <option value="org">Everyone at KFintech</option>
            <option value="committee">Committees only</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="d-vis-reason">Reason</label>
          <textarea
            id="d-vis-reason"
            rows={2}
            value={visReason}
            onChange={(e) => setVisReason(e.target.value)}
          />
        </div>
        <button type="submit" className="button button-secondary" disabled={busy}>
          Change visibility
        </button>
      </form>

      <div>
        <h3>Hold</h3>
        {pendingHold ? (
          <div className="notice" role="group" aria-labelledby="hold-confirm">
            <p id="hold-confirm">
              Hold this as {pendingHold}? It leaves the queue until a second reviewer confirms.
            </p>
            <div className="button-row">
              <button
                type="button"
                className="button"
                disabled={busy}
                onClick={() => {
                  const kind = pendingHold;
                  setPendingHold(null);
                  void send({ action: "hold", kind }, "Hold requested. A second reviewer confirms.");
                }}
              >
                Yes, hold as {pendingHold}
              </button>
              <button
                type="button"
                className="button button-secondary"
                disabled={busy}
                onClick={() => setPendingHold(null)}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="button-row">
            <button
              type="button"
              className="button button-secondary"
              disabled={busy}
              onClick={() => setPendingHold("spam")}
            >
              Hold as spam
            </button>
            <button
              type="button"
              className="button button-secondary"
              disabled={busy}
              onClick={() => setPendingHold("abuse")}
            >
              Hold as abuse
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
