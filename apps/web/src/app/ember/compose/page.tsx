import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { BANNERS } from "@/lib/killswitch-routes";
import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { emberCurrent, emberIssue } from "@/server/ember";

import { IssueView } from "../issue-view";
import { ApproveNote, NoteForm, SendIssue, StartDraft } from "./actions";

export const metadata: Metadata = { title: "Write The Ember" };
export const dynamic = "force-dynamic";

/** This month's issue: an admin opens it, the chair writes or approves the note, and an admin who did neither
 * sends it (BLD-128, BLD-134). */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "write_ember_note")) redirect("/");
  const current = await emberCurrent(me).catch(() => null);
  if (current === null)
    return <p className="notice">We can&apos;t load The Ember just now. Please try again in a minute.</p>;
  if (current.id === null)
    return (
      <>
        <h1>Write The Ember</h1>
        {can(me.roles, "send_ember") ? (
          <StartDraft />
        ) : (
          <p>No issue is open yet. An admin starts each month&apos;s issue.</p>
        )}
      </>
    );
  const issue = await emberIssue(me, String(current.id)).catch(() => null);
  if (issue === null)
    return <p className="notice">We can&apos;t load the draft just now. Please try again in a minute.</p>;
  const blocked = issue.ember_paused
    ? BANNERS["ember.send"]
    : issue.ones_paused
      ? BANNERS["ones.public"]
      : !issue.note
        ? "Add the chair's note before sending."
        : null;
  return (
    <>
      <h1>Write The Ember, {issue.month_label}</h1>
      <p className="lead">
        This is how the issue reads now. It is built from what everyone may already see, and fills in as the
        month goes on.
      </p>
      <section aria-labelledby="c-note">
        <h2 id="c-note">The chair&apos;s note</h2>
        <p className="muted">
          {issue.note_approved
            ? "The chair has approved this note. Changing it sends it back to the chair."
            : "Waiting for the chair to approve the note. An admin may draft it; it is the chair's once approved."}
        </p>
        <NoteForm id={issue.id} initial={issue.note} />
        {issue.can_approve_note ? <ApproveNote id={issue.id} /> : null}
      </section>
      {can(me.roles, "send_ember") ? (
        <section aria-labelledby="c-send">
          <h2 id="c-send">Send</h2>
          {issue.can_send && issue.confirm_token ? (
            <SendIssue id={issue.id} blocked={blocked} confirmToken={issue.confirm_token} />
          ) : (
            <p className="notice">
              {issue.own_note
                ? "You wrote or approved this note, so another admin sends the issue."
                : "The issue can go out once the chair has approved the note."}
            </p>
          )}
        </section>
      ) : null}
      <h2>Preview</h2>
      <IssueView issue={issue} />
    </>
  );
}
