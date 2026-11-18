/**
 * S-ONE's field rules and words (V-FIELDS.one, L-ONES), mirrored from the worker (services/worker/wall/common.py),
 * which checks every one of them again. Pure, so the unit tests read them directly.
 */
export const MSG_OUT_OF_RANGE = "Pick a number from 1 to 999.";
export const MSG_BRIEF = "Keep it to one sentence, up to 140 characters.";
export const MSG_SAVE_FAILED = "Couldn't save that. Try again.";

// S-ONE's states the board does not draw (BLD-E041). Each line below waits for HR's sign-off (docs/BUILD_LOG.md).
/** L-ONES.rules/5: a proposed brief waits for the programme team. */
// NOT DRAWN (BLD-E041): HR sign-off
export const MSG_BRIEF_PENDING =
  "Your new brief is with the programme team. It goes on the Wall once they approve it.";
// NOT DRAWN (BLD-E041): HR sign-off
export const MSG_NO_BRIEF = "No brief on the Wall yet.";
/** "Propose a new brief" opens a field in the card. */
// NOT DRAWN (BLD-E041): HR sign-off
export const BRIEF_FIELD = "Your new brief";
// NOT DRAWN (BLD-E041): HR sign-off
export const briefCount = (n: number) => `${n} of 140 characters`;
// NOT DRAWN (BLD-E041): HR sign-off
export const BRIEF_SEND = "Send for approval";
// NOT DRAWN (BLD-E041): HR sign-off
export const BRIEF_CANCEL = "Cancel";
/** L-IMPACT/4's words, in a tile the board does not draw empty. */
// NOT DRAWN (BLD-E041): HR sign-off
export const BEING_MEASURED = "Being measured";
// NOT DRAWN (BLD-E041): HR sign-off
export const LOAD_FAILED = "We can't load your One dashboard just now. Please try again in a minute.";
/** F-COPY.states/3's one way on from the error state. */
// NOT DRAWN (BLD-E041): HR sign-off
export const TRY_AGAIN = "Try again";

/**
 * S-ONE.rules/1: only the worker's own 403 `not_a_one` sends a person to Profile. Any other refusal (a role the
 * worker refuses, a kill switch) is not a statement that they are not a One, so the screen shows its error state.
 */
export function isNotAOne(status: number | undefined, body: unknown): boolean {
  if (status !== 403 || !body || typeof body !== "object") return false;
  const error = (body as { error?: unknown }).error;
  return !!error && typeof error === "object" && (error as { code?: unknown }).code === "not_a_one";
}

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

/** Where a moment whose "seen" did not land waits for the next load (S-ONE.rules/3). Holds the moment's id only. */
export const UNSENT_SEEN_KEY = "one.glow-up.unsent";

/** Remembers on this device that the moment played but its "seen" did not land. */
export function rememberUnsentSeen(store: Store | null, id: number | string): void {
  try {
    store?.setItem(UNSENT_SEEN_KEY, String(id));
  } catch {
    // No storage (private mode, blocked): the moment plays again next time, as before.
  }
}

/**
 * True when this moment already played here and its "seen" did not land: the caller sends "seen" once more instead
 * of playing it again. The note is used up either way, so the retry happens once (S-ONE.rules/3, L-ONES.rules/3).
 */
export function takeUnsentSeen(store: Store | null, id: number | string): boolean {
  try {
    const was = store?.getItem(UNSENT_SEEN_KEY) ?? null;
    if (was !== null) store?.removeItem(UNSENT_SEEN_KEY);
    return was === String(id);
  } catch {
    return false;
  }
}

/** V-FIELDS.one/1: a whole number from 1 to 999, or null. */
export function wholeNumber(raw: string): number | null {
  const t = raw.trim();
  if (!/^\d{1,3}$/.test(t)) return null;
  const n = Number(t);
  return n >= 1 && n <= 999 ? n : null;
}

/** V-FIELDS.one/4: one sentence, 20 to 140 characters, as the worker reads it (spaces collapsed). */
export function briefProblem(text: string): string | null {
  const clean = text.split(/\s+/).filter(Boolean).join(" ");
  if (clean.length < 20 || clean.length > 140 || /[.!?]\s+\S/.test(clean)) return MSG_BRIEF;
  return null;
}

/** "620 hours a month" → "620" and "hours a month"; "₹18 lakh a year" → "₹18" and "lakh a year" (S-ONE.layout/5). */
export function splitFigure(value: string): { big: string; unit: string } {
  const m = /^(₹?\s?\d[\d,]*(?:\.\d+)?)(?:\s+(.+))?$/.exec(value.trim());
  return m ? { big: m[1]!, unit: m[2] ?? "" } : { big: value, unit: "" };
}
