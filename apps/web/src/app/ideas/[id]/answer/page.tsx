import type { Metadata } from "next";
import { redirect } from "next/navigation";

import type { SharerQuestionSetResponse } from "@/lib/contracts";
import { currentUser } from "@/server/auth/current";
import { deskRead } from "@/server/desk";
import { isOn, switchStates } from "@/server/killswitch";

import { AnswerView } from "./answer-view";
import "./answer.css";

export const metadata: Metadata = { title: "Answer the review desk" };
export const dynamic = "force-dynamic";

/** S-R3 Answer the review desk: the only place the desk's questions are answered, one at a time (L-QUESTIONS.answer).
 * The worker answers "not found" to anyone but the idea's sharer. */
export default async function AnswerPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const { id } = await params;
  const [set, states] = await Promise.all([
    deskRead<SharerQuestionSetResponse>(me, `/internal/ideas/${encodeURIComponent(id)}/question-set`),
    switchStates().catch(() => new Map<string, "on" | "off">()),
  ]);
  // "Hide it for me" on an answer's file waits for `files.blackout` (off at launch, DEC-107), as on Check it and the
  // edit page; an unread switch counts as off (BLD-B275).
  return <AnswerView ideaId={id} initial={set ?? null} blackout={isOn(states, "files.blackout")} />;
}
