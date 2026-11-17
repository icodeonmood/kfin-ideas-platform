/**
 * The draft card on S-02's "Session expired mid-draft" (L-AUTH.states, A-API.auth `expired` with `draft?`): the
 * title, when and on which device it was saved, the step, and what is kept (L-AUTH.rules/5: sorting and hidden
 * details intact).
 *
 * Drafts are `ideas` rows with status 'draft' (lane E's cut-over, 20261121500100: title, step, saved_at,
 * saved_device, archived_at, sorting_sources, sorting_confirmed_at), owned through contributor_map; hidden details
 * are `hidden_details` rows (the kind only, never the value). The title is the masked one (L-HIDE), shown only to
 * the browser that held this person's session. No draft, or one without a title yet: the card is left out.
 */
import { getDb } from "../db";

/** E-ENUMS.hidden kinds in plain words, one and several. */
const KIND_WORDS: Record<string, [string, string]> = {
  folio: ["folio", "folios"],
  pan: ["PAN", "PANs"],
  phone: ["phone number", "phone numbers"],
  email: ["email address", "email addresses"],
  account: ["account number", "account numbers"],
  aadhaar: ["Aadhaar number", "Aadhaar numbers"],
  name: ["name", "names"],
};

/**
 * S-02's kept line, built from the draft (BLD-A179). The board draws one case, "Sorting and the folio you hid are
 * kept."; the others follow its words: "Sorting is kept.", "The folio you hid is kept.", "Sorting and the 2 folios you
 * hid are kept.", "Sorting and the details you hid are kept." (several kinds). Sorting counts once the person has
 * confirmed or changed it (E-ENUMS sorting_source); a suggestion they never touched is simply suggested again.
 * Nothing kept: null, and the card leaves the line out.
 */
export function keptLine(kept: { sorting: boolean; hidden: string[] }): string | null {
  const kinds = [...new Set(kept.hidden)];
  let hid: string | null = null;
  if (kept.hidden.length === 1) hid = `the ${KIND_WORDS[kinds[0]!]?.[0] ?? "detail"} you hid`;
  else if (kept.hidden.length > 1)
    hid =
      kinds.length === 1 && KIND_WORDS[kinds[0]!]
        ? `the ${kept.hidden.length} ${KIND_WORDS[kinds[0]!]![1]} you hid`
        : "the details you hid";
  if (kept.sorting && hid) return `Sorting and ${hid} are kept.`;
  if (kept.sorting) return "Sorting is kept.";
  if (hid) return `${hid[0]!.toUpperCase()}${hid.slice(1)} ${kept.hidden.length === 1 ? "is" : "are"} kept.`;
  return null;
}

/** Whether the person has confirmed the sorting or changed any of it (`sorting_sources`: {field: {source, why}}). */
export function sortingTouched(confirmedAt: unknown, sources: unknown): boolean {
  if (confirmedAt) return true;
  if (!sources || typeof sources !== "object" || Array.isArray(sources)) return false;
  return Object.values(sources as Record<string, unknown>).some((v) => {
    const source = v && typeof v === "object" ? (v as { source?: unknown }).source : v;
    return source === "confirmed" || source === "changed";
  });
}

export type DraftCard = {
  id: string;
  title: string;
  savedAt: Date;
  /** The device it was last saved on, as the composer recorded it. */
  savedOn: "laptop" | "phone" | null;
  /** E-ENUMS draft step: tell, check:1 to check:7, send. */
  step: string;
  /** What is kept, in the composer's words ("Sorting and the folio you hid are kept."), or null. */
  keptLine: string | null;
};

export interface DraftLookup {
  /** The draft, only if it belongs to this person and is still a draft. */
  card(ownerId: string, draftId: string): Promise<DraftCard | null>;
}

export const pgDraftLookup: DraftLookup = {
  async card(ownerId, draftId) {
    const row = await getDb()
      .selectFrom("ideas")
      .innerJoin("contributor_map", "contributor_map.contributor_code", "ideas.contributor_code")
      .select([
        "ideas.id",
        "ideas.title",
        "ideas.saved_at",
        "ideas.saved_device",
        "ideas.step",
        "ideas.sorting_confirmed_at",
        "ideas.sorting_sources",
      ])
      .where("ideas.id", "=", draftId)
      .where("contributor_map.user_id", "=", ownerId)
      .where("ideas.status", "=", "draft")
      .where("ideas.archived_at", "is", null)
      .executeTakeFirst();
    if (!row || !row.title || !row.saved_at) return null;
    const hidden = await getDb()
      .selectFrom("hidden_details")
      .select("kind")
      .where("idea_uuid", "=", row.id)
      .where("state", "=", "hidden")
      .execute();
    const device = row.saved_device === "laptop" || row.saved_device === "phone" ? row.saved_device : null;
    return {
      id: row.id,
      title: row.title,
      savedAt: new Date(row.saved_at),
      savedOn: device,
      step: row.step ?? "tell",
      keptLine: keptLine({
        sorting: sortingTouched(row.sorting_confirmed_at, row.sorting_sources),
        hidden: hidden.map((h) => h.kind),
      }),
    };
  },
};

let lookup: DraftLookup = pgDraftLookup;

export const draftLookup = () => lookup;

export function setDraftLookup(next: DraftLookup) {
  lookup = next;
}
