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

describe("S-R2.left/2 fileHref: Open goes through lane C's view route, which applies DEC-107 (BLD-B243)", () => {
  it("every listed file opens through /api/files/:id/view, a customer detail included", () => {
    expect(fileHref({ id: "ATT-2026-000101" })).toBe("/api/files/ATT-2026-000101/view");
    expect(fileHref({ id: "ATT-2026-000102", file_state: "checked", state: "clean" })).toBe(
      "/api/files/ATT-2026-000102/view",
    );
    expect(fileHref({ id: "ATT-2026-000105", customer_detail: true })).toBe(
      "/api/files/ATT-2026-000105/view",
    );
    expect(fileHref({ id: "ATT-2026-000106", file_state: "personal_data_found" })).toBe(
      "/api/files/ATT-2026-000106/view",
    );
    expect(fileHref({ id: "ATT 7/x" })).toBe("/api/files/ATT%207%2Fx/view");
  });

  it("a row with no id gets no Open, and fileHref is the view route", () => {
    expect(fileHref({ customer_detail: false })).toBeNull();
    expect(filesViewRoute({})).toBeNull();
    expect(fileHref({ id: "ATT-2026-000107" })).toBe(filesViewRoute({ id: "ATT-2026-000107" }));
  });
});
