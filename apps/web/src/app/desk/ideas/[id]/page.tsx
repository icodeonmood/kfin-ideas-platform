import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import type { ReviewerIdeaResponse, SuggestedQuestionsResponse } from "@/lib/contracts";
import { currentUser } from "@/server/auth/current";
import { can } from "@/lib/rbac";
import { deskOpen, deskRead } from "@/server/desk";
import { promises } from "@/server/promises";

import { ReviewerIdea, type ReviewPromises } from "./reviewer-idea";
import "../../desk.css";
import "./reviewer.css";

export const metadata: Metadata = { title: "Review an idea" };
export const dynamic = "force-dynamic";

/** S-R2: everything a reviewer needs to decide on one idea, on one page. */
export default async function ReviewerIdeaPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const { id } = await params;
  // L-REVIEW.open/1 (J-REVIEW/1): a reviewer who may act opens the idea before it is read, so the page already shows
  // it opened and the sharer's edit window is closed. Idempotent; the worker leaves a reviewer's own idea alone.
  if (can(me.roles, "work_review_queue")) await deskOpen(me, id);
  const [page, suggested, p] = await Promise.all([
    deskRead<ReviewerIdeaResponse>(me, `/internal/desk/ideas/${encodeURIComponent(id)}`),
    deskRead<SuggestedQuestionsResponse>(
      me,
      `/internal/desk/ideas/${encodeURIComponent(id)}/suggested-questions`,
    ).catch(() => null),
    promises(),
  ]);
  if (!page) notFound();
  const numbers: ReviewPromises = {
    reasonMin: p.notes.decision_reason_min_chars,
    mergeNoteMin: p.notes.merge_note_min_chars,
    answerDays: p.questions.answer_options_days,
    answerDefaultDays: p.questions.answer_default_days,
    deadlineHour: p.questions.deadline_hour,
    extendDays: p.questions.extend_by_days,
    returnMonths: p.not_now.return_options_months,
    returnDefaultMonths: p.not_now.return_default_months,
    windowDays: p.committee_window.days,
    windowMaxMonths: p.committee_window.max_months,
  };
  return (
    <ReviewerIdea
      key={`${page.panel.state}:${page.idea.status}`}
      page={page}
      suggested={suggested ?? []}
      numbers={numbers}
    />
  );
}
