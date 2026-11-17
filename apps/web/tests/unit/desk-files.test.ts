/** DEC-107 on the review side (BLD-B238, BLD-B243): a file holding a customer detail is labelled and its Open says so;
 * Open goes only where a route serves the file. */
import { describe, expect, it } from "vitest";

import { CUSTOMER_DETAIL, fileHref, filesViewRoute, openFileName } from "@/lib/desk/files";

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

describe("S-R2.left/2 fileHref: Open only where today's route serves the file (BLD-B243)", () => {
  it("a checked file, or one from before the new pipeline, opens through the attachments route", () => {
    expect(fileHref({ id: "ATT-2026-000101" })).toBe("/api/attachments/ATT-2026-000101");
    expect(fileHref({ id: "ATT-2026-000102", file_state: "checked", state: "clean" })).toBe(
      "/api/attachments/ATT-2026-000102",
    );
    expect(fileHref({ id: "ATT-2026-000103", file_state: "hidden_checked" })).toBe(
      "/api/attachments/ATT-2026-000103",
    );
    expect(fileHref({ id: "ATT-2026-000104", file_state: null, state: "clean" })).toBe(
      "/api/attachments/ATT-2026-000104",
    );
  });

  it("a file holding a customer detail, or not checked, gets no Open: that route would answer a raw 403", () => {
    expect(fileHref({ id: "ATT-2026-000105", customer_detail: true })).toBeNull();
    expect(fileHref({ id: "ATT-2026-000106", file_state: "personal_data_found" })).toBeNull();
    expect(fileHref({ id: "ATT-2026-000107", file_state: "checking" })).toBeNull();
    expect(fileHref({ id: "ATT-2026-000108", file_state: null, state: "quarantined" })).toBeNull();
    expect(fileHref({ customer_detail: false })).toBeNull();
  });

  it("lane C's view route is ready for the one-line switch, and opens every listed file", () => {
    expect(filesViewRoute({ id: "ATT-2026-000105", customer_detail: true })).toBe(
      "/api/files/ATT-2026-000105/view",
    );
    expect(filesViewRoute({})).toBeNull();
  });
});
