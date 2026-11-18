/**
 * Home's data (S-03, A-API.home), read from the routes that already exist rather than one new `GET /home` (the brief
 * for BLD-C143): lane E's `GET /api/me/ideas` gives "Your ideas" and the ideas that need the person; lane B's
 * `GET /api/ideas/{id}/question-set` gives each one's questions for C-QCARD; lane F's `GET /api/crew?limit=3` gives
 * the crew cards (`CrewDeckResponse`, private by DEC-104); `GET /api/ones/posts` gives the Ones.
 * Each part loads on its own and a part that cannot be read is left out of the screen, so one slow route never
 * holds up the box at the top. Nothing here logs words.
 */
import type {
  CrewCard,
  CrewDeckResponse,
  MyIdeaRow,
  MyIdeasResponse,
  OnePost,
  SharerQuestionSetResponse,
} from "@/lib/contracts";

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

/** S-03.sections/2: up to three of the person's own shared ideas, newest activity first. */
export const IDEAS_SHOWN = 3;
/** S-03.sections/1: the top two items that need the person. */
export const NEEDS_SHOWN = 2;
/** S-03.sections/3: the top three crew matches. */
export const CREW_SHOWN = 3;

export type OpenSet = NonNullable<SharerQuestionSetResponse>;

export interface HomeMine {
  ideas: { total: number; top: MyIdeaRow[] };
  needs: { total: number; rows: MyIdeaRow[] };
  drafts: number;
}

/** An `OnePost` as the worker sends it: with its id and whether this person cheered it. */
export type HomePost = OnePost & { id: string; liked?: boolean };

async function readJson<T>(f: FetchLike, path: string): Promise<T | null> {
  let res: Response;
  try {
    res = await f(path, { cache: "no-store", headers: { Accept: "application/json" } });
  } catch {
    return null;
  }
  if (!res.ok) return null;
  return (await res.json().catch(() => null)) as T | null;
}

/** "Your ideas" (shared ones only: drafts sit in the side bar) and the ideas whose status is Needs you. */
export async function loadMine(f: FetchLike): Promise<HomeMine | null> {
  const body = await readJson<MyIdeasResponse>(f, "/api/me/ideas?list=yours&sort=latest");
  if (!body || !Array.isArray(body.items)) return null;
  const shared = body.items.filter((r) => r.group !== "drafts" && !r.archived);
  const counts = body.counts ?? ({} as MyIdeasResponse["counts"]);
  const sharedTotal =
    typeof counts.all === "number" && typeof counts.drafts === "number"
      ? Math.max(0, counts.all - counts.drafts)
      : shared.length;
  const needing = shared.filter((r) => r.pill?.status === "needs_you" || r.group === "needs_you");
  return {
    ideas: { total: sharedTotal, top: shared.slice(0, IDEAS_SHOWN) },
    needs: {
      total: typeof counts.needs_you === "number" ? counts.needs_you : needing.length,
      rows: needing.slice(0, NEEDS_SHOWN),
    },
    drafts: typeof counts.drafts === "number" ? counts.drafts : 0,
  };
}

/** The open question set on each idea that needs the person (null when it has none). */
export async function loadSets(f: FetchLike, rows: MyIdeaRow[]): Promise<{ ideaId: string; set: OpenSet }[]> {
  const sets = await Promise.all(
    rows.map(async (r) => {
      const set = await readJson<SharerQuestionSetResponse>(
        f,
        `/api/ideas/${encodeURIComponent(r.id)}/question-set`,
      );
      return set && Array.isArray(set.questions) ? { ideaId: r.id, set } : null;
    }),
  );
  return sets.filter((s): s is { ideaId: string; set: OpenSet } => s !== null);
}

/** Find your crew's top three from lane F's deck (L-CREW/10: its first cards and how many there are in all); null
 * when the crew route cannot be read, so Home shows no state rather than "No one close to yours yet". */
export async function loadCrew(f: FetchLike): Promise<{ total: number; top: CrewCard[] } | null> {
  const body = await readJson<Pick<CrewDeckResponse, "items" | "total">>(f, `/api/crew?limit=${CREW_SHOWN}`);
  if (!body || !Array.isArray(body.items)) return null;
  return {
    total: typeof body.total === "number" ? body.total : body.items.length,
    top: body.items.slice(0, CREW_SHOWN),
  };
}

/** The Ones' posts for the fan, newest first; null when they cannot be read (or the Ones are paused). */
export async function loadOnes(f: FetchLike): Promise<HomePost[] | null> {
  const body = await readJson<HomePost[] | { items?: HomePost[] }>(f, "/api/ones/posts");
  if (!body) return null;
  const list = Array.isArray(body) ? body : Array.isArray(body.items) ? body.items : null;
  return list ? list.filter((p) => p && typeof p.text === "string" && p.one) : null;
}

/** Cheer or un-cheer a One's post; the new count when the server says it. */
export async function cheer(f: FetchLike, postId: string, liked: boolean): Promise<number | null> {
  try {
    const res = await f(`/api/ones/posts/${encodeURIComponent(postId)}/like`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ liked }),
    });
    if (!res.ok) return null;
    const out = (await res.json().catch(() => null)) as { likes?: unknown } | null;
    return out && typeof out.likes === "number" ? out.likes : null;
  } catch {
    return null;
  }
}
