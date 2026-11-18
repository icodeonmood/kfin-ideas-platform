/**
 * Similar ideas and the idea preview (L-SIMILAR, A-API.idea-preview), web side. The worker builds both from the
 * database and decides what this person may see (DEC-104): masked text only, names unless hidden from the Wall,
 * and `compare` for the review desk and the Ones Committee alone. The web app only vouches for who is asking.
 */
import type { IdeaPreview, SimilarMatch } from "@/lib/contracts/entities";

import type { CurrentUser } from "./auth/current";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

const IDEA_REF = /^IDEA-[0-9]{4}-[0-9]{6}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** An idea's IDEA- reference or its row ID (a draft has only the second). */
export const isIdeaKey = (value: string): boolean => IDEA_REF.test(value) || UUID.test(value);

/** GET /api/ideas/:id/preview[?compare_with=<id>] (BLD-C090). */
export async function ideaPreview(
  me: CurrentUser,
  ideaKey: string,
  compareWith?: string | null,
): Promise<IdeaPreview> {
  if (!isIdeaKey(ideaKey)) throw new SubmissionError(404, "not_found");
  if (compareWith && !isIdeaKey(compareWith)) throw new SubmissionError(400, "bad_compare_with");
  const q = new URLSearchParams({ user_id: me.id });
  if (compareWith) q.set("compare_with", compareWith);
  const res = await workerFetch(`/internal/ideas/${encodeURIComponent(ideaKey)}/preview?${q.toString()}`);
  if (res.status === 404) throw new SubmissionError(404, "not_found");
  if (!res.ok) throw new SubmissionError(502, "preview_unavailable");
  return (await res.json()) as IdeaPreview;
}

/** GET /api/ideas/:id/similar (BLD-C092): the sharer's own draft or idea, or any idea for the desk and committee. */
export async function similarIdeas(me: CurrentUser, ideaKey: string): Promise<SimilarMatch[]> {
  if (!isIdeaKey(ideaKey)) throw new SubmissionError(404, "not_found");
  const q = new URLSearchParams({ user_id: me.id });
  const res = await workerFetch(`/internal/ideas/${encodeURIComponent(ideaKey)}/similar?${q.toString()}`);
  if (res.status === 404) throw new SubmissionError(404, "not_found");
  if (!res.ok) throw new SubmissionError(502, "similar_unavailable");
  return (await res.json()) as SimilarMatch[];
}

/** POST /api/ideas/:id/similar/keep-separate { on? } (BLD-C095): "Keep mine separate" (or, with on: false, "Show
 * them again") on the sharer's own unsent draft. */
export async function keepSeparate(
  me: CurrentUser,
  ideaKey: string,
  on: boolean,
): Promise<{ kept_separate: boolean; found_while_drafting: number }> {
  if (!isIdeaKey(ideaKey)) throw new SubmissionError(404, "not_found");
  const res = await workerFetch(`/internal/ideas/${encodeURIComponent(ideaKey)}/similar/keep-separate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: me.id, on }),
  });
  if (res.status === 404) throw new SubmissionError(404, "not_found");
  if (!res.ok) throw new SubmissionError(502, "keep_separate_failed");
  return (await res.json()) as { kept_separate: boolean; found_while_drafting: number };
}
