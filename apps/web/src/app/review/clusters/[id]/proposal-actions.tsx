"use client";

/** Review desk actions on a group proposal (§4.4 B step 8): approve with edits, remove a member, reject. */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import type { ProposalView } from "@/server/clusters";

const ERRORS: Record<string, string> = {
  already_decided: "This proposal has already been decided.",
  own_idea: "You cannot decide a group that holds your own idea. Another reviewer will take it.",
  split_coming_soon: "Splitting a group from this screen is coming soon.",
  cluster_changed: "One of the groups changed since this proposal was made. Wait for the next weekly run.",
  too_few_members: "A group needs at least two ideas that are still open.",
  name_required: "Please write a name for the group.",
  description_required: "Please write a one-sentence description.",
  problem_required: "Please write the combined problem.",
  name_length: "The name should be 3 to 80 characters.",
  name_too_long: "Please keep the name to 8 words or fewer.",
  name_not_card_safe:
    "Everyone in the group sees the name, so it cannot name a person, client or company, or hold an ID.",
  description_length: "The description should be 10 to 220 characters.",
  problem_length: "The problem should be 20 to 1,500 characters.",
  description_not_card_safe:
    "Everyone can see the description, so it cannot name a person, client or company, or hold an ID.",
  personal_data: "Please take out personal details first.",
  reason_code_required: "Please choose a reason.",
  not_a_member: "That idea is not in this proposal.",
  remove_not_available: "Members can be removed only from a new group or a group that grows.",
  note_length: "Please keep the note under 1,000 characters.",
};

const STATE_WORDS: Record<string, string> = {
  approved: "This proposal was approved",
  rejected: "This proposal was turned down",
  superseded: "A newer weekly run replaced this proposal",
};

const REJECT: [string, string][] = [
  ["not_same_problem", "These are not the same problem"],
  ["too_broad", "The group is too broad"],
  ["too_narrow", "The group is too narrow"],
  ["wrong_cluster", "They belong with another group"],
  ["other", "Something else"],
];
const REMOVE: [string, string][] = [
  ["not_same_problem", "Not the same problem"],
  ["too_broad", "Makes the group too broad"],
  ["other", "Something else"],
];

export function ProposalActions({ id, view }: { id: string; view: ProposalView }) {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [name, setName] = useState(view.summary?.name ?? "");
  const [description, setDescription] = useState(view.summary?.description ?? "");
  const [problem, setProblem] = useState(view.summary?.problem ?? "");
  const [removeId, setRemoveId] = useState(view.members[0]?.idea_id ?? "");
  const [removeCode, setRemoveCode] = useState("not_same_problem");
  const [rejectCode, setRejectCode] = useState("not_same_problem");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const open = view.state === "open";

  async function send(body: Record<string, unknown>, done: string) {
    setBusy(true);
    setMessage(null);
    const res = await fetch(`/api/review/cluster-proposals/${id}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { error?: string; cluster_id?: string } | null;
    setBusy(false);
    setMessage(
      res?.ok
        ? { text: out?.cluster_id ? `${done} The group is ${out.cluster_id}.` : done, error: false }
        : { text: ERRORS[String(out?.error)] ?? "That did not go through. Please try again.", error: true },
    );
    statusRef.current?.focus();
    if (res?.ok) router.refresh();
  }

  const status = (
    <p
      ref={statusRef}
      tabIndex={-1}
      role="status"
      aria-live="polite"
      className={message?.error ? "field-error" : "muted"}
    >
      {message?.text ?? ""}
    </p>
  );

  if (!open || !view.may_act)
    return (
      <section aria-labelledby="p-actions" className="panel">
        <h2 id="p-actions">Actions</h2>
        {status}
        <p>
          {!open
            ? `${STATE_WORDS[view.state] ?? view.state}${view.cluster_id ? `: ${view.cluster_id}` : ""}.`
            : "Only the review desk can decide group proposals."}
        </p>
      </section>
    );

  const editable = view.kind !== "split";
  const real = view.mode === "real";
  // Only what the desk changed is sent; untouched text stays exactly as stored (tags included).
  const changes = () => {
    const out: Record<string, string> = {};
    if (!real) return out;
    if (name !== (view.summary?.name ?? "")) out.name = name;
    if (description !== (view.summary?.description ?? "")) out.description = description;
    if (problem !== (view.summary?.problem ?? "")) out.problem = problem;
    return out;
  };
  return (
    <section aria-labelledby="p-actions" className="panel">
      <h2 id="p-actions">Actions</h2>
      {status}
      {editable ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send({ action: "approve", ...changes() }, "Approved.");
          }}
        >
          <h3>Approve</h3>
          <p className="muted">Edit the text first if it needs it. Contributors are told once you approve.</p>
          {real ? (
            <>
              <div className="field">
                <label htmlFor="cp-name">Name (8 words or fewer)</label>
                <input id="cp-name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="cp-description">Description (everyone can see this)</label>
                <textarea
                  id="cp-description"
                  rows={2}
                  maxLength={220}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="cp-problem">Combined problem</label>
                <textarea
                  id="cp-problem"
                  rows={5}
                  maxLength={1500}
                  value={problem}
                  onChange={(e) => setProblem(e.target.value)}
                />
              </div>
            </>
          ) : (
            <p className="notice">
              You see labels in place of names, so you can approve the text as it is but not edit it. The
              reviewer handling this proposal can edit it.
            </p>
          )}
          <button type="submit" className="button" disabled={busy}>
            Approve this group
          </button>
        </form>
      ) : null}

      {view.kind === "new" || view.kind === "grow" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send({ action: "remove_member", idea_id: removeId, reason_code: removeCode }, "Removed.");
          }}
        >
          <h3>Remove a member</h3>
          <p className="muted">The idea will not be put with these ideas again.</p>
          <div className="field">
            <label htmlFor="cp-remove">Idea</label>
            <select id="cp-remove" value={removeId} onChange={(e) => setRemoveId(e.target.value)}>
              {view.members.map((m) => (
                <option key={m.idea_id} value={m.idea_id}>
                  {m.idea_id}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="cp-remove-why">Why</label>
            <select id="cp-remove-why" value={removeCode} onChange={(e) => setRemoveCode(e.target.value)}>
              {REMOVE.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="button button-secondary" disabled={busy || !removeId}>
            Remove from this proposal
          </button>
        </form>
      ) : (
        <p className="notice">
          Coming soon: moving single ideas between groups and merging into a group the batch did not name.
        </p>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send(
            { action: "reject", reason_code: rejectCode, note },
            "Turned down. The batch will keep these apart.",
          );
        }}
      >
        <h3>Turn down</h3>
        <div className="field">
          <label htmlFor="cp-reject-why">Why</label>
          <select id="cp-reject-why" value={rejectCode} onChange={(e) => setRejectCode(e.target.value)}>
            {REJECT.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="cp-reject-note">Note for the desk (optional)</label>
          <textarea
            id="cp-reject-note"
            rows={2}
            maxLength={1000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <button type="submit" className="button button-secondary" disabled={busy}>
          Turn down this proposal
        </button>
      </form>
    </section>
  );
}
