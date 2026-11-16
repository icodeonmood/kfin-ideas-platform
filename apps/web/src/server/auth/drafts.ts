/**
 * The draft card on S-02's "Session expired mid-draft" (L-AUTH.states, A-API.auth `expired` with `draft?`): the
 * title, when and on which device it was saved, and the step.
 *
 * Drafts are `ideas` rows with status 'draft' (lane E's cut-over, 20261121500100: title, step, saved_at,
 * saved_device, archived_at), owned through contributor_map. The title is the masked one (L-HIDE), shown only to
 * the browser that held this person's session. No draft, or one without a title yet: the card is left out.
 */
import { getDb } from "../db";

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
      .select(["ideas.id", "ideas.title", "ideas.saved_at", "ideas.saved_device", "ideas.step"])
      .where("ideas.id", "=", draftId)
      .where("contributor_map.user_id", "=", ownerId)
      .where("ideas.status", "=", "draft")
      .where("ideas.archived_at", "is", null)
      .executeTakeFirst();
    if (!row || !row.title || !row.saved_at) return null;
    const device = row.saved_device === "laptop" || row.saved_device === "phone" ? row.saved_device : null;
    return {
      id: row.id,
      title: row.title,
      savedAt: new Date(row.saved_at),
      savedOn: device,
      step: row.step ?? "tell",
      keptLine: null,
    };
  },
};

let lookup: DraftLookup = pgDraftLookup;

export const draftLookup = () => lookup;

export function setDraftLookup(next: DraftLookup) {
  lookup = next;
}
