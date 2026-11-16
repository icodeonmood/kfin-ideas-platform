/**
 * The draft card on S-02's "Session expired mid-draft" (L-AUTH.states, A-API.auth `expired` with `draft?`): the
 * title, when and on which device it was saved, and the step.
 *
 * Drafts are `ideas` rows with status 'draft' (lane E's cut-over, 20261121500100: title, step, saved_at,
 * saved_device, archived_at), owned through contributor_map. Before the cut-over is on a database those columns
 * are missing, and the lookup finds nothing: the expired state then shows without the card (BLD-A174).
 */
import { sql } from "kysely";

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

const MISSING = new Set(["42P01", "42703"]); // undefined table, undefined column

export const pgDraftLookup: DraftLookup = {
  async card(ownerId, draftId) {
    try {
      const r = await sql<{
        id: string;
        title: string | null;
        saved_at: Date | null;
        saved_device: "laptop" | "phone" | null;
        step: string | null;
      }>`
        SELECT i.id, i.title, i.saved_at, i.saved_device, i.step
        FROM ideas i JOIN contributor_map m ON m.contributor_code = i.contributor_code
        WHERE i.id = ${draftId}::uuid AND m.user_id = ${ownerId}::uuid
          AND i.status = 'draft' AND i.archived_at IS NULL
      `.execute(getDb());
      const row = r.rows[0];
      if (!row || !row.title || !row.saved_at) return null;
      return {
        id: row.id,
        title: row.title,
        savedAt: new Date(row.saved_at),
        savedOn: row.saved_device,
        step: row.step ?? "tell",
        keptLine: null,
      };
    } catch (err) {
      if (MISSING.has(String((err as { code?: unknown }).code))) return null;
      throw err;
    }
  },
};

let lookup: DraftLookup = pgDraftLookup;

export const draftLookup = () => lookup;

export function setDraftLookup(next: DraftLookup) {
  lookup = next;
}
