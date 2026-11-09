import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { emberCurrent, emberIssue } from "@/server/ember";

import { IssueView } from "../issue-view";
import { NoteForm, SendIssue, StartDraft } from "./actions";

export const metadata: Metadata = { title: "Write The Ember" };
export const dynamic = "force-dynamic";

/** This month's issue: an admin opens it, the chair writes the note, an admin sends it (BLD-128). */
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
    ? "Sending The Ember is paused for now."
    : issue.ones_paused
      ? "The Ones are resting from the wall, so The Ember can't go out just now."
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
        <NoteForm id={issue.id} initial={issue.note} />
      </section>
      {issue.can_send ? (
        <section aria-labelledby="c-send">
          <h2 id="c-send">Send</h2>
          <SendIssue id={issue.id} blocked={blocked} />
        </section>
      ) : null}
      <h2>Preview</h2>
      <IssueView issue={issue} />
    </>
  );
}
