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
