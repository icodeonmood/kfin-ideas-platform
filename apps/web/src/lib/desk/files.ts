/**
 * Files on the review side that hold a customer detail (DEC-107): the scan found one, and until "Hide it for me" is
 * solid for the file's type the file still goes through, opened only by the sharer, the review desk and the Ones
 * Committee. Wherever such a file is listed it carries a visible label, and its "Open" control says so in its name,
 * so the mark is never colour or position alone (BLD-B238).
 */
export const CUSTOMER_DETAIL = "Has a customer detail";

/** The accessible name of a file's "Open": "Open branch-call-log.pdf", or with ", which has a customer detail". */
export function openFileName(name: string, customerDetail: boolean): string {
  return customerDetail ? `Open ${name}, which has a customer detail` : `Open ${name}`;
}

/** What a file row knows about its file. The reviewer's page sends `customer_detail`; a row that also carries the
 * file's states (the old `state`, the new `file_state`) is judged on them too. */
export type DeskFile = {
  id?: string | null;
  customer_detail?: boolean;
  file_state?: string | null;
  state?: string | null;
};

/** The states lane C's route opens a stored copy in (`VIEWABLE` in services/worker/attachments/files.py): checked,
 * hidden_checked, and personal_data_found, which DEC-107 opens for the review desk and the Ones Committee. A link's
 * `ok` is not one: links are never fetched (non-negotiable 8). */
const VIEWABLE: ReadonlySet<string> = new Set(["checked", "hidden_checked", "personal_data_found"]);

/**
 * Whether the file has passed its checks. The new pipeline's `file_state` decides when there is one (a found file's
 * old `state` stays `quarantine`, so it is not read then); a file from before the cut-over has only the old `state`,
 * whose `clean` is checked. Nothing else opens (non-negotiable 8): lane C's route answers 403 for it, so no "Open" is
 * offered and the row shows with its label only (BLD-B243).
 */
function passedChecks(file: DeskFile): boolean {
  if (file.file_state != null) return VIEWABLE.has(file.file_state);
  return file.state == null || file.state === "clean";
}

/** Lane C's `GET /api/files/:id/view` (A-API.files, C-FILE.view): the checked copy, for the review desk and the Ones
 * Committee too when the file holds a customer detail (DEC-107). It decides and audits each opening itself. */
export function filesViewRoute(file: DeskFile): string | null {
  return file.id ? `/api/files/${encodeURIComponent(file.id)}/view` : null;
}

/** Where a file's "Open" goes on the review side, or null when the file has not passed its checks (no "Open" is
 * shown). A file holding a customer detail opens here, for the desk and the committee only (DEC-107; BLD-B251). */
export function fileHref(file: DeskFile): string | null {
  return passedChecks(file) ? filesViewRoute(file) : null;
}
