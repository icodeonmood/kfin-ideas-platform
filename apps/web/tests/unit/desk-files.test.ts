/** DEC-107 on the review side (BLD-B238): a file holding a customer detail is labelled and its Open says so. */
import { describe, expect, it } from "vitest";

import { CUSTOMER_DETAIL, openFileName } from "@/lib/desk/files";

describe("DEC-107: files with a customer detail, on S-R2 and C-QCARD", () => {
  it("the label is plain words, never colour alone", () => {
    expect(CUSTOMER_DETAIL).toBe("Has a customer detail");
  });

  it("Open names the file, and the customer detail when there is one", () => {
    expect(openFileName("branch-call-log-nov.pdf", false)).toBe("Open branch-call-log-nov.pdf");
    expect(openFileName("rejection-sms-1.png", true)).toBe(
      "Open rejection-sms-1.png, which has a customer detail",
    );
  });
});
