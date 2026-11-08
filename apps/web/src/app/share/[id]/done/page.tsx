import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { getDraft, SubmissionError } from "@/server/submissions";

export const metadata: Metadata = { title: "Your idea is in" };
export const dynamic = "force-dynamic";

export default async function Done({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  let row;
  try {
    row = await getDraft(me, id);
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  if (row.stage === "draft") redirect(`/share/${id}`);
  return (
    <>
      <h1>Your idea is in: {row.idea_id}</h1>
      <p className="lead">Thank you. Here is what happens next.</p>
      <ol className="steps">
        <li>We check it for personal data and suggest answers for anything you left blank.</li>
        <li>We look for colleagues who raised the same thing, so you can team up.</li>
        <li>The review desk looks at it within 5 working days. You will hear from us at each step.</li>
      </ol>
      <p>
        <Link href="/my-ideas">Track your idea in My ideas</Link>
      </p>
    </>
  );
}
