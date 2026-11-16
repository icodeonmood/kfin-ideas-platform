import { describe, expect, it } from "vitest";

import { clockTime, isFailureRef, newFailureRef, referenceLabel } from "@/server/auth/reference";
import { callbackErrorOutcome, failurePath } from "@/server/auth/sso";

describe("L-AUTH.rules/8: every sign-in failure has a reference the IT service desk can find", () => {
  it("is SSO- and four hex digits, with the time in India", () => {
    for (let i = 0; i < 50; i++) expect(newFailureRef()).toMatch(/^SSO-[0-9A-F]{4}$/);
    const at = Date.UTC(2026, 10, 20, 4, 12) / 1000; // 9:42 am IST
    expect(referenceLabel("SSO-7F3A", at)).toBe("SSO-7F3A, 9:42 am");
    expect(clockTime(new Date(Date.UTC(2026, 10, 20, 9, 5)))).toBe("2:35 pm");
    expect(referenceLabel("SSO-7F3A", null)).toBe("SSO-7F3A");
  });

  it("only a well-formed reference is shown back (nothing else from the address bar)", () => {
    expect(isFailureRef("SSO-7F3A")).toBe(true);
    for (const bad of ["SSO-7f3a", "SSO-7F3A<script>", "7F3A", undefined, ""])
      expect(isFailureRef(bad)).toBe(false);
    expect(failurePath("failed", "SSO-7F3A", new Date(at(0)))).toBe("/sign-in?failed=SSO-7F3A&at=0");
  });
});

describe("L-AUTH.rules/1: silent single sign-on", () => {
  it("a silent try the provider cannot finish alone shows S-02; any other error is a failure", () => {
    for (const e of [
      "login_required",
      "interaction_required",
      "consent_required",
      "account_selection_required",
    ]) {
      expect(callbackErrorOutcome(e, true)).toBe("show_sign_in");
      expect(callbackErrorOutcome(e, false)).toBe("failed");
    }
    expect(callbackErrorOutcome("temporarily_unavailable", true)).toBe("failed");
    expect(callbackErrorOutcome("server_error", true)).toBe("failed");
  });
});

function at(seconds: number) {
  return seconds * 1000;
}
