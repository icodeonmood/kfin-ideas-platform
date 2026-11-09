import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { day } from "@/lib/dates";
import { currentUser } from "@/server/auth/current";
import { emberIssue } from "@/server/ember";
import { SubmissionError } from "@/server/submissions";

import { IssueView } from "../issue-view";

export const metadata: Metadata = { title: "The Ember" };
export const dynamic = "force-dynamic";

/** One issue: a sent one for everyone; a draft only for the chair and admins (the worker decides). */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const issue = await emberIssue(me, (await params).id).catch((err: unknown) => {
    if (err instanceof SubmissionError && err.status === 404) return undefined;
    return null;
  });
  if (issue === undefined) notFound();
  if (issue === null)
    return <p className="notice">We can&apos;t load this issue just now. Please try again in a minute.</p>;
  return (
    <>
      <div className="brand-band">
        <h1>The Ember, {issue.month_label}</h1>
        <p className="lead">
          {issue.state === "sent" && issue.sent_at
            ? `Sent ${day(issue.sent_at)}.`
            : "Draft. Only the chair and admins can see it."}
        </p>
      </div>
      <IssueView issue={issue} />
      <p>
        <Link href="/ember">All issues</Link>
      </p>
    </>
  );
}
