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

/** The new pipeline's checked states. Only these read `state = 'clean'` in the old column (lane C, 17 Nov). */
const CHECKED: ReadonlySet<string> = new Set(["checked", "hidden_checked", "ok"]);

/**
 * Today's route, `GET /api/attachments/:id`: it serves a file whose old state is clean, to its owner and the review
 * desk, and answers anything else with a raw 403 (or 404). So it is offered only for a file it serves: checked, or
 * from before the new pipeline, and never one holding a customer detail. The row still shows, with its label, but
 * without "Open" (BLD-B243).
 */
function attachmentsRoute(file: DeskFile): string | null {
  if (!file.id || file.customer_detail) return null;
  if (file.file_state != null && !CHECKED.has(file.file_state)) return null;
  if (file.state != null && file.state !== "clean") return null;
  return `/api/attachments/${encodeURIComponent(file.id)}`;
}

/** Lane C's `GET /api/files/:id/view` (A-API.files): it applies DEC-107 itself, committee roles included, so every
 * listed file opens through it. */
export function filesViewRoute(file: DeskFile): string | null {
  return file.id ? `/api/files/${encodeURIComponent(file.id)}/view` : null;
}

/** The one place the review side chooses a file's route. When lane C's route is on main, this line becomes
 * `const route = filesViewRoute;` and nothing else changes. */
const route: (file: DeskFile) => string | null = attachmentsRoute;

/** Where a file's "Open" goes, or null when no route can open it for this viewer yet (no "Open" is shown). */
export function fileHref(file: DeskFile): string | null {
  return route(file);
}
