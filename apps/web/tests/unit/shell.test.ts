/**
 * The shell (lane D; C-SIDEBAR, C-PHONE-TABS, C-TASKBAR, C-AVATAR; F-SPACE.shell, F-COLOR.glass; BLD-D011): which
 * chrome a path gets, its ambient light, the current-page rule, the fold cookie and the shell's words.
 */
import { describe, expect, it } from "vitest";

import { foldedFrom, foldValue } from "@/components/shell/fold";
import { lightFor, shellMode } from "@/components/shell/frame";
import { IconAdmin, NavIcon } from "@/components/shell/icons";
import { isCurrent } from "@/components/shell/sidebar";
import { saveWords, savedTime } from "@/components/shell/taskbar";
import rbac from "@/lib/rbac.json";
import { initialsOf, toneFor, whenSaved } from "@/server/shell";

const DRAFT = "3f2b1c9e-8a7d-4e6f-9b0a-1c2d3e4f5a6b";

describe("F-SPACE.shell: the chrome each path gets", () => {
  it.each([
    ["/launch", true, "display"],
    ["/constellation", true, "display"],
    ["/display/office", false, "display"],
    ["/sign-in", false, "public"],
    ["/", false, "public"],
    ["/share", true, "task"],
    [`/share/${DRAFT}`, true, "task"],
    [`/share/${DRAFT}/check`, true, "task"],
    ["/ideas/IDEA-2026-001473/edit", true, "task"],
    ["/ideas/IDEA-2026-001473/answer", true, "task"],
    ["/ideas/IDEA-2026-001473/conversation", true, "task"],
    ["/kit/conversation", true, "app"],
    [`/share/${DRAFT}/done`, true, "app"],
    ["/share/examples/sms-codes", true, "app"],
    ["/", true, "app"],
    ["/wall", true, "app"],
    ["/ideas/IDEA-2026-001473", true, "app"],
  ] as const)("%s (signed in: %s) is %s", (path, signedIn, mode) => {
    expect(shellMode(path, signedIn)).toBe(mode);
  });

  it("F-COLOR.glass/1–2: full light on browsing screens, quiet light where people work", () => {
    expect(lightFor("/", "app")).toBe("full");
    expect(lightFor("/share", "task")).toBe("full");
    expect(lightFor("/wall", "app")).toBe("full");
    expect(lightFor(`/share/${DRAFT}/check`, "task")).toBe("quiet");
    expect(lightFor("/my-ideas", "app")).toBe("quiet");
    expect(lightFor("/review", "app")).toBe("quiet");
    expect(lightFor("/inbox", "app")).toBe("quiet");
    expect(lightFor("/sign-in", "public")).toBe("full");
  });
});

describe("C-SIDEBAR", () => {
  it("C-SIDEBAR.states: Home is current only on its own path; other items on their path and below", () => {
    expect(isCurrent("/", "/")).toBe(true);
    expect(isCurrent("/wall", "/")).toBe(false);
    expect(isCurrent("/review/7", "/review")).toBe(true);
    expect(isCurrent("/reviewers", "/review")).toBe(false);
  });

  it("C-SIDEBAR.fold/3: the fold choice is the person's own, so a shared device starts open for the next person", () => {
    expect(foldedFrom(foldValue("u-1", true), "u-1")).toBe(true);
    expect(foldedFrom(foldValue("u-1", false), "u-1")).toBe(false);
    expect(foldedFrom(foldValue("u-1", true), "u-2")).toBeNull();
    expect(foldedFrom(undefined, "u-1")).toBeNull();
  });

  it("C-SIDEBAR.anatomy/4: dots are warn for needs you, blue for active, neutral otherwise", () => {
    expect(toneFor("needs_info")).toBe("warn");
    expect(toneFor("scanned")).toBe("blue");
    expect(toneFor("in_delivery")).toBe("blue");
    expect(toneFor("shipped")).toBe("neutral");
    expect(toneFor("withdrawn")).toBe("neutral");
  });

  it("a draft says when it was last saved, in India time", () => {
    const now = new Date("2026-11-16T12:00:00+05:30");
    expect(whenSaved("2026-11-16T09:00:00+05:30", now)).toBe("Today");
    expect(whenSaved("2026-11-15T23:30:00+05:30", now)).toBe("Yesterday");
    expect(whenSaved("2026-11-13T10:00:00+05:30", now)).toBe("Friday");
    expect(whenSaved("2026-11-02T10:00:00+05:30", now)).toBe("2 Nov");
    expect(whenSaved(null, now)).toBe("");
  });
});

describe("C-AVATAR", () => {
  it("C-AVATAR.anatomy: two initials, upper case", () => {
    expect(initialsOf("Synthetic Newcomer")).toBe("SN");
    expect(initialsOf("  asha  ")).toBe("AS");
    expect(initialsOf("Ravi Kumar Nair")).toBe("RN");
    expect(initialsOf("")).toBe("?");
  });
});

describe("C-TASKBAR.save", () => {
  it("each save state has its words", () => {
    expect(saveWords("idle")).toBe("Saves as you type");
    expect(saveWords("saving")).toBe("Saving…");
    expect(saveWords("saved", "2026-11-16T08:08:00Z")).toBe("Saved at 1:38 pm");
    expect(saveWords("offline")).toBe("Unsaved, you’re offline");
    expect(saveWords("changed")).toBe("Unsaved changes");
  });

  it("times are India time, lower-case am and pm", () => {
    expect(savedTime("2026-11-16T04:35:00Z")).toBe("10:05 am");
  });
});

describe("C-BUTTON", () => {
  it("C-BUTTON.variants and sizes map to the stylesheet's classes", async () => {
    const { buttonClass } = await import("@/components/ui/button");
    expect(buttonClass()).toBe("btn btn-primary");
    expect(buttonClass("line", "sm")).toBe("btn btn-secondary btn-sm");
    expect(buttonClass("soft", "full")).toBe("btn btn-soft btn-full");
    expect(buttonClass("text", "full")).toBe("tb");
    expect(buttonClass("text-blue")).toBe("tb blue");
    expect(buttonClass("primary", "regular", "tbar-close")).toBe("btn btn-primary tbar-close");
  });
});

describe("C-AVATAR.crew", () => {
  it("the crew line leads with the lead's name or counts colleagues", async () => {
    const { crewLine } = await import("@/components/ui/avatar");
    const four = [{ name: "a" }, { name: "b" }, { name: "c" }, { name: "d" }];
    expect(crewLine(four, 4, "Rahul Verma")).toBe("Rahul Verma and 3 others on it");
    expect(crewLine(four.slice(0, 2), 2, "Rahul Verma")).toBe("Rahul Verma and 1 other on it");
    expect(crewLine(four.slice(0, 1), 1, "Rahul Verma")).toBe("Rahul Verma is on it");
    expect(crewLine(four)).toBe("4 colleagues on it");
    expect(crewLine([], 0)).toBe("Nobody on it yet");
  });
});

describe("C-SIDEBAR.anatomy: every navigation row has its own icon", () => {
  // rbac.json's navigation keys (Find your crew, `crew`, among them), plus lane E's account rows (S-H6 Profile, S-ONE
  // dashboard) as they land.
  const keys = [...rbac.navigation.map((n) => n.key), "profile", "one"].filter((k) => k !== "admin");
  it("S-H2: the navigation includes Find your crew", () => expect(keys).toContain("crew"));
  it.each(keys)("%s is not drawn with the default (Admin) icon", (navKey) => {
    expect(NavIcon({ navKey }).type).not.toBe(IconAdmin);
  });
});
