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

describe("S-R2.left/2 fileHref: Open goes through lane C's view route once the file has passed its checks (BLD-B243, BLD-B251)", () => {
  it("a checked file, or one from before the new pipeline, opens through /api/files/:id/view", () => {
    expect(fileHref({ id: "ATT-2026-000101" })).toBe("/api/files/ATT-2026-000101/view");
    expect(fileHref({ id: "ATT-2026-000102", file_state: "checked", state: "clean" })).toBe(
      "/api/files/ATT-2026-000102/view",
    );
    expect(fileHref({ id: "ATT-2026-000103", file_state: "hidden_checked" })).toBe(
      "/api/files/ATT-2026-000103/view",
    );
    expect(fileHref({ id: "ATT-2026-000104", file_state: null, state: "clean" })).toBe(
      "/api/files/ATT-2026-000104/view",
    );
  });

  it("DEC-107: a file holding a customer detail opens for the desk and the committee, though its old state is quarantine", () => {
    expect(
      fileHref({
        id: "ATT-2026-000105",
        customer_detail: true,
        file_state: "personal_data_found",
        state: "quarantine",
      }),
    ).toBe("/api/files/ATT-2026-000105/view");
    expect(fileHref({ id: "ATT-2026-000109", customer_detail: true })).toBe(
      "/api/files/ATT-2026-000109/view",
    );
  });

  it("non-negotiable 8: a file not yet checked, or failed, gets no Open (the route answers 403), nor does a link", () => {
    expect(fileHref({ id: "ATT-2026-000107", file_state: "checking" })).toBeNull();
    expect(fileHref({ id: "ATT-2026-000110", file_state: "infected", state: "rejected" })).toBeNull();
    expect(fileHref({ id: "ATT-2026-000111", file_state: "ok" })).toBeNull();
    expect(fileHref({ id: "ATT-2026-000108", file_state: null, state: "quarantined" })).toBeNull();
    expect(fileHref({ customer_detail: false })).toBeNull();
  });

  it("the view route's address, for any file with an id", () => {
    expect(filesViewRoute({ id: "ATT-2026-000105", customer_detail: true })).toBe(
      "/api/files/ATT-2026-000105/view",
    );
    expect(filesViewRoute({})).toBeNull();
  });
});
