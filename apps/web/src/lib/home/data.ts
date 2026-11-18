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

type Read<T> = { ok: true; body: T | null } | { ok: false };

/** One read, telling a read that failed (no answer, an error status, not JSON) from one that answered null. */
async function read<T>(f: FetchLike, path: string): Promise<Read<T>> {
  let res: Response;
  try {
    res = await f(path, { cache: "no-store", headers: { Accept: "application/json" } });
  } catch {
    return { ok: false };
  }
  if (!res.ok) return { ok: false };
  try {
    return { ok: true, body: (await res.json()) as T | null };
  } catch {
    return { ok: false };
  }
}

async function readJson<T>(f: FetchLike, path: string): Promise<T | null> {
  const got = await read<T>(f, path);
  return got.ok ? got.body : null;
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

export type NeedsCard = { ideaId: string; set: OpenSet };
/** One idea's question-set read: its open set, null when it has none, or `failed` when it could not be read. */
export type SetRead = { ideaId: string; set: OpenSet | null; failed: boolean };

/** Each idea's read of its open question set, in the rows' order. */
export async function readSets(f: FetchLike, rows: MyIdeaRow[]): Promise<SetRead[]> {
  return Promise.all(
    rows.map(async (r): Promise<SetRead> => {
      const got = await read<SharerQuestionSetResponse>(
        f,
        `/api/ideas/${encodeURIComponent(r.id)}/question-set`,
      );
      if (!got.ok) return { ideaId: r.id, set: null, failed: true };
      const set = got.body;
      return { ideaId: r.id, set: set && Array.isArray(set.questions) ? set : null, failed: false };
    }),
  );
}

/** The open question set on each idea that needs the person; an idea with none, or whose read failed, is left out. */
export async function loadSets(f: FetchLike, rows: MyIdeaRow[]): Promise<NeedsCard[]> {
  return (await readSets(f, rows)).flatMap((r) => (r.set ? [{ ideaId: r.ideaId, set: r.set }] : []));
}

/**
 * Needs you's cards after a re-read (S-03.sections/1): an idea whose set was read shows what came back (its open
 * set, or no card when it has none); an idea whose read failed keeps the card it had. When every read failed the
 * list stays as it was: null, "keep what is shown".
 */
export function keepFailedSets(before: NeedsCard[], reads: SetRead[]): NeedsCard[] | null {
  if (reads.length > 0 && reads.every((r) => r.failed)) return null;
  return reads.flatMap((r) =>
    r.failed ? before.filter((c) => c.ideaId === r.ideaId) : r.set ? [{ ideaId: r.ideaId, set: r.set }] : [],
  );
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
