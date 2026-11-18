// @vitest-environment jsdom
/**
 * S-06's "Ask to join the build team" after a Pick (L-DECIDE/6, A-API `POST /ideas/:id/join-build`; J-REVIEW/6;
 * BLD-E055). The button shows while lane B's `join_build.can_ask` says so; a click posts with no body and the drawn
 * line, "Asked. The build lead replies by 27 November.", takes its place, takes focus (which reads it out once; it is not also put in the status line).
 * Asked before: the line, no button. No `join_build`: nothing. A refusal: the screen's "try again" line and a refresh,
 * with focus kept off the page's body. No Undo (A-API has no withdraw). Copy: Status.md, Status.dc.html:899.
 * Synthetic people only.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh, replace: () => undefined, push: () => undefined }),
  useParams: () => ({ id: "IDEA-2026-001481" }),
  usePathname: () => "/ideas/IDEA-2026-001481",
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("@/lib/motion/spark", () => ({ sparkBurst: vi.fn() }));
vi.mock("@/components/teamup/teamup-sheet", async (actual) => ({
  ...(await actual<typeof import("@/components/teamup/teamup-sheet")>()),
  useTeamUpSheet: () => ({ open: vi.fn(), close: vi.fn(), isOpen: false, sheet: null }),
}));

const { SharerScreen } = await import("@/app/ideas/[id]/sharer-screen");
const { askedLine, dayMonth } = await import("@/app/ideas/[id]/join-build");
type Props = Parameters<typeof SharerScreen>[0];

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- Fixtures (synthetic) --------------------------------------------------------------------------------------
const REF = "IDEA-2026-001481";
const ASK = "Ask to join the build team";
const ASKED = "Asked. The build lead replies by 27 November.";
const TRY_AGAIN = "We can't do that just now. Please try again in a minute.";
const CAN_ASK = { can_ask: true, asked_at: null, reply_by: "2026-11-27" };
const ASKED_BEFORE = { can_ask: false, asked_at: "2026-11-17T09:00:00Z", reply_by: "2026-11-27" };

function decision(joinBuild: unknown, reversed = false) {
  return {
    window_id: "w-1",
    kind: "decision",
    idea: { id: REF, title: "Investors call to ask why a redemption was rejected", meta: "" },
    sharer: { id: "p-k", name: "Kavya Iyer", first_name: "Kavya", initials: "KI" },
    decision: {
      choice: "pick",
      label: "Picked",
      merged_into: null,
      by_line: "by the review desk, Monday 16 November",
      reason: "A clear problem, a real number and a simple fix. Synthetic.",
      reason_heading: "The review desk’s reason",
    },
    window: { state: reversed ? "reversed" : "open" },
    reversal: reversed ? { to: "not_now", note: "Synthetic note." } : null,
    decided_at: "2026-11-16T06:00:00Z",
    return_at: null,
    lines: {
      joined_line: null,
      committee_line:
        "The Ones Committee can review this decision until Wednesday 16 December. If they change it, their note comes to your Inbox. After that, it stands.",
      reversal: null,
    },
    joined_into: null,
    ...(joinBuild === undefined ? {} : { join_build: joinBuild }),
  };
}

function props(joinBuild: unknown, reversed = false): Props {
  return {
    view: {
      view: "sharer",
      screen: "S-06",
      idea: {
        id: REF,
        ref: REF,
        title: "Investors call to ask why a redemption was rejected",
        status: "picked",
        stages: [{ stage: "built", state: "now", detail: "Team chosen by Friday 27 November" }],
        own_words: [],
        hidden: [],
        files: [],
        has_open_questions: false,
        kept_separate: false,
      },
      page: {
        state: "picked",
        state_label: "",
        pill: { status: "picked", label: "Picked", variant: "ok" },
        breadcrumb: { label: "My ideas", to: "/my-ideas", current: REF },
        shared_label: null,
        first_arrival: false,
        card: null,
        card_from: "decision",
        window: null,
        actions: {},
        lane_b: { question_set: "", decision: "" },
        shared: {
          intro: "",
          rows: [],
          hidden: { chips: [], more: 0, note: "", all: [] },
          attached: { label: "Attached", files: [], answers: [] },
          fix: { label: "Your fix", answers: [] },
        },
        conversation: null,
        similar: { heading: "", intro: "", tiles: [] },
        merged: null,
        own_words_unmasked: false,
      },
    },
    decision: decision(joinBuild, reversed),
    questions: null,
    partFailed: false,
  } as unknown as Props;
}

// --- Rendering --------------------------------------------------------------------------------------------------
let host: HTMLDivElement;
let root: Root | null = null;

function show(p: Props) {
  act(() => root!.render(createElement(SharerScreen, p)));
}
const button = (name: string) =>
  Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((b) => b.textContent?.trim() === name);
const joined = () => host.querySelector<HTMLElement>(".ip-joined");
const said = () => host.querySelector('[role="status"]')?.textContent ?? "";
const settle = () => new Promise((r) => setTimeout(r, 0));

async function click(b: HTMLButtonElement) {
  await act(async () => {
    b.focus();
    b.click();
    await settle();
  });
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  refresh.mockClear();
});
afterEach(() => {
  act(() => root?.unmount());
  root = null;
  host.remove();
  vi.unstubAllGlobals();
});

describe("L-DECIDE/6, S-06 Picked: Ask to join the build team", () => {
  it("L-DECIDE/6: the button shows when join_build.can_ask, as a plain button on the card", () => {
    show(props(CAN_ASK));
    const b = button(ASK);
    expect(b).toBeTruthy();
    expect(b!.getAttribute("type")).toBe("button");
    expect(b!.closest(".ip-card-body")).toBeTruthy();
    expect(joined()).toBeNull();
  });

  it("A-API join-build: a click posts to /api/ideas/:id/join-build with no body", async () => {
    const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(
      async () => new Response(JSON.stringify({ asked_at: "2026-11-18T09:30:00Z" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    show(props(CAN_ASK));
    await click(button(ASK)!);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe(`/api/ideas/${REF}/join-build`);
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeUndefined();
  });

  it("J-REVIEW/6: on 200 the drawn line with the reply-by date replaces the button and takes focus, heard once", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ asked_at: "2026-11-18T09:30:00Z" }), { status: 200 })),
    );
    show(props(CAN_ASK));
    await click(button(ASK)!);
    expect(button(ASK)).toBeUndefined();
    expect(joined()?.textContent).toBe(ASKED);
    expect(joined()?.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    expect(said()).toBe(""); // focus reads the line; the status line stays quiet, so it is heard once
    expect(document.activeElement).toBe(joined());
    expect(host.textContent).not.toContain(TRY_AGAIN);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("L-DECIDE/6: asked before (asked_at on load), the line shows and no button", () => {
    show(props(ASKED_BEFORE));
    expect(button(ASK)).toBeUndefined();
    expect(joined()?.textContent).toBe(ASKED);
  });

  it("BLD-E055: without a reply-by date the line drops its date clause", () => {
    show(props({ ...ASKED_BEFORE, reply_by: null }));
    expect(joined()?.textContent).toBe("Asked. The build lead replies.");
  });

  it("no join_build (another viewer, or lane B's field not there yet): nothing shows and no error", () => {
    show(props(null));
    expect(button(ASK)).toBeUndefined();
    expect(joined()).toBeNull();
    show(props(undefined));
    expect(button(ASK)).toBeUndefined();
    expect(joined()).toBeNull();
    expect(host.textContent).not.toContain(TRY_AGAIN);
    expect(host.querySelector('[role="alert"]')).toBeNull();
  });

  it("can_ask false and not asked: no button", () => {
    show(props({ can_ask: false, asked_at: null, reply_by: "2026-11-27" }));
    expect(button(ASK)).toBeUndefined();
    expect(joined()).toBeNull();
  });

  it("reversed by the Ones Committee: neither the button nor the asked line", () => {
    show(props(ASKED_BEFORE, true));
    expect(joined()).toBeNull();
    expect(button(ASK)).toBeUndefined();
  });

  it("409 not_picked: the screen's try-again line, a refresh, and focus to the title when the button goes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ error: "not_picked" }), { status: 409 })),
    );
    show(props(CAN_ASK));
    await click(button(ASK)!);
    expect(host.textContent).toContain(TRY_AGAIN);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(joined()).toBeNull();
    // The refreshed page: lane B no longer offers the ask, so the button goes and focus lands on the title
    show(props({ can_ask: false, asked_at: null, reply_by: "2026-11-27" }));
    expect(button(ASK)).toBeUndefined();
    expect(host.textContent).toContain(TRY_AGAIN);
    expect(document.activeElement?.id).toBe("ip-title");
  });

  it("409 team_chosen, 403 and a dropped connection: try again and a refresh", async () => {
    for (const reply of [
      () => new Response(JSON.stringify({ error: "team_chosen" }), { status: 409 }),
      () => new Response(JSON.stringify({ error: "forbidden" }), { status: 403 }),
      () => {
        throw new TypeError("network");
      },
    ]) {
      refresh.mockClear();
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => reply()),
      );
      show(props(CAN_ASK));
      await click(button(ASK)!);
      expect(host.textContent).toContain(TRY_AGAIN);
      expect(refresh).toHaveBeenCalledTimes(1);
      // The button still applies: focus stays on it
      expect(document.activeElement).toBe(button(ASK));
    }
  });

  it("BLD-E055: no Undo beside the button or the asked line", async () => {
    show(props(CAN_ASK));
    expect(button("Undo")).toBeUndefined();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ asked_at: "2026-11-18T09:30:00Z" }), { status: 200 })),
    );
    await click(button(ASK)!);
    expect(button("Undo")).toBeUndefined();
    expect(host.textContent).not.toContain("Undo");
    show(props(ASKED_BEFORE));
    expect(button("Undo")).toBeUndefined();
  });
});

describe("BLD-E055: the asked line's date", () => {
  it("day and month only, in office time (India)", () => {
    expect(dayMonth("2026-11-27")).toBe("27 November");
    expect(dayMonth("2026-11-27T20:00:00Z")).toBe("28 November");
    expect(dayMonth(null)).toBeNull();
    expect(dayMonth("not a date")).toBeNull();
    expect(askedLine("2026-11-27")).toBe(ASKED);
    expect(askedLine(null)).toBe("Asked. The build lead replies.");
  });
});
