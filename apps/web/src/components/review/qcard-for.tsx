"use client";

/**
 * C-QCARD read from the sharer's own question set, for a host that knows only the set's id (S-08's `questions`
 * entry, BLD-B249). The first read of a set marks it seen for the desk (L-QUESTIONS.clock/1), so the read names the
 * set (`?set_id=`): when the open set is another, the route answers 404 and marks nothing. Until the set arrives, or
 * when it cannot be read, the host's `fallback` shows.
 */
import { useEffect, useState, type ComponentProps, type ReactNode } from "react";

import type { SharerQuestionSetResponse } from "@/lib/contracts";

import { QuestionsCard } from "./qcard";

type Set = NonNullable<SharerQuestionSetResponse>;

/** The set as `GET /ideas/:id/question-set` sends it, with what the card reads. */
function isSet(data: unknown): data is Set {
  const s = data as Partial<Set> | null;
  return (
    !!s &&
    typeof s.id === "string" &&
    typeof s.by?.first_name === "string" &&
    typeof s.deadline === "string" &&
    typeof s.answered === "number" &&
    typeof s.count === "number" &&
    Array.isArray(s.questions) &&
    s.questions.length > 0 &&
    s.questions.every((q) => typeof q?.id === "string" && typeof q.text === "string")
  );
}

/** The sharer's set `setId` on idea `ideaId`, or null (not theirs, not open, another set, or the read failed). */
export async function readQuestionSet(ideaId: string, setId: string): Promise<Set | null> {
  try {
    const res = await fetch(
      `/api/ideas/${encodeURIComponent(ideaId)}/question-set?set_id=${encodeURIComponent(setId)}`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    const set: unknown = await res.json();
    return isSet(set) && set.id === setId ? set : null;
  } catch {
    return null;
  }
}

type CardProps = Omit<ComponentProps<typeof QuestionsCard>, "ideaId" | "set">;

export function QuestionsCardFor({
  ideaId,
  setId,
  fallback,
  ...card
}: CardProps & { ideaId: string; setId: string; fallback: ReactNode }) {
  const [set, setSet] = useState<Set | null>(null);
  useEffect(() => {
    let live = true;
    void readQuestionSet(ideaId, setId).then((s) => live && setSet(s));
    return () => {
      live = false;
    };
  }, [ideaId, setId]);
  return set ? <QuestionsCard ideaId={ideaId} set={set} {...card} /> : <>{fallback}</>;
}
