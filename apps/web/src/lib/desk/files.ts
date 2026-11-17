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

/** Lane C's `GET /api/files/:id/view` (A-API.files): it applies DEC-107 itself, committee roles included, so every
 * listed file opens through it. */
export function filesViewRoute(file: DeskFile): string | null {
  return file.id ? `/api/files/${encodeURIComponent(file.id)}/view` : null;
}

/**
 * Where a file's "Open" goes, or null when the row has no id (no "Open" is shown). Every file the review side lists
 * opens through lane C's view route, which decides who may open what (DEC-107: a file holding a customer detail
 * opens for the sharer, the review desk and the Ones Committee); it replaced the old `/api/attachments/:id`, which
 * served only clean files and answered the rest with a raw 403 (BLD-B243, lane C's c/hide-3).
 */
export function fileHref(file: DeskFile): string | null {
  return filesViewRoute(file);
}
