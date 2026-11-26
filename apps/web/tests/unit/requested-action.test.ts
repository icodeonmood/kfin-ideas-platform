// @vitest-environment jsdom
/**
 * DEC-126 (WF-03b, BLD-F094): `RequestedAction`, "Requested" with "Withdraw" where "Team up" was, as a host such as
 * Home's crew card (S-03, lane C) drops it in: the inactive but focusable "Requested" marked as the opener, the
 * "Withdraw" link calling `DELETE /api/team-up/:id` for either kind, busy while it goes, `onWithdrawn` with the same
 * `TeamUpSent` the sheet hands over, focus to the host's "Team up" drawn again, and a failed withdraw saying why.
 * BLD-F105: focus reaches "Team up" whether the next frame or the host's redraw comes first (J-TEAMUP/3c).
 * Both are lane D's shared `Button` (BLD-D019): "Requested" `inactive`, "Withdraw" `variant="quiet"` (BLD-F096).
 * Synthetic people only: the pack's fictional cast (Kavya asks, Ravi leads).
 */
import { act, createElement, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/motion/spark", () => ({ sparkBurst: vi.fn() }));

const { REQUESTED_COPY, RequestedAction } = await import("@/components/teamup/requested-action");
const { teamUpOpener } = await import("@/components/teamup/teamup-sheet");
type Sent = import("@/components/teamup/teamup-sheet").TeamUpSent;

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const IDEA = "IDEA-2026-001412";
const TITLE = "Rejection SMS codes confuse investors";

type Answer = { status: number; body: unknown; wait?: Promise<void> };
let answer: Answer = { status: 200, body: {} };
let calls: { url: string; method: string }[] = [];
let host: HTMLElement;
let root: Root;

beforeEach(() => {
  calls = [];
  answer = {
    status: 200,
    body: { id: "req-7", request: "teamup", idea_id: IDEA, state: "withdrawn", after: null },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      calls.push({ url, method: init.method ?? "GET" });
      if (answer.wait) await answer.wait;
      return {
        ok: answer.status < 300,
        status: answer.status,
        json: () => Promise.resolve(answer.body),
      };
    }),
  );
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
async function settle(ms = 40) {
  await act(async () => {
    await new Promise((r) => setTimeout(r, ms));
  });
}

/** How the host redraws after a withdraw: from its own state at once (Home, Find your crew), after a while (a host that
 * refreshes), or not at all (a host that keeps the pair). */
type Redraw = "now" | "later" | "never";

/** A host card: "Team up" (marked as the opener) until asked; then RequestedAction; back to "Team up" on withdraw. */
function Card({
  kind = "teamup",
  id = "req-7",
  title,
  redraw = "now",
  log,
}: {
  kind?: "teamup" | "merge";
  id?: string;
  title?: string;
  redraw?: Redraw;
  log: Sent[];
}) {
  const [asked, setAsked] = useState(true);
  return asked
    ? createElement(RequestedAction, {
        ideaId: IDEA,
        title,
        request: { id, kind },
        onWithdrawn: (s: Sent) => {
          log.push(s);
          if (redraw === "now") setAsked(false);
          else if (redraw === "later") setTimeout(() => setAsked(false), 0);
        },
      })
    : createElement(
        "button",
        { type: "button", className: "btn btn-primary", ...teamUpOpener(IDEA) },
        "Team up",
      );
}

type Mount = { kind?: "teamup" | "merge"; id?: string; title?: string; redraw?: Redraw };

async function mount(props: Mount = {}) {
  const log: Sent[] = [];
  await act(async () => root.render(createElement(Card, { ...props, log })));
  return log;
}

describe("RequestedAction (DEC-126)", () => {
  it("Requested is inactive but focusable and read out, marked where Team up was; Withdraw is its own quiet link", async () => {
    await mount({ title: TITLE });
    const [requested, withdraw] = Array.from(document.querySelectorAll("button"));
    expect(text(requested)).toBe("Requested");
    expect(requested!.getAttribute("aria-disabled")).toBe("true");
    expect(requested!.hasAttribute("disabled")).toBe(false);
    expect(requested!.getAttribute("aria-label")).toBe(`Requested: you asked to team up on ${TITLE}`);
    expect(requested!.getAttribute("data-teamup-opener")).toBe(IDEA);
    // lane D's shared looks (BLD-D019, BLD-F096): the host's "Team up" variant and size, inactive
    expect(requested!.className).toBe("btn btn-primary btn-full is-inactive");
    requested!.focus();
    expect(document.activeElement).toBe(requested);
    await act(async () => requested!.click());
    expect(calls).toEqual([]);
    expect(text(withdraw)).toBe("Withdraw");
    expect(withdraw!.className).toBe("link-quiet");
    expect(withdraw!.getAttribute("aria-label")).toBe(`Withdraw your request to team up on ${TITLE}`);
    expect(requested!.contains(withdraw!)).toBe(false);
    // No live region: focus on "Team up" after a withdraw says what changed.
    expect(document.querySelector("[aria-live], [role='status']")).toBeNull();
  });

  it("without a title the names are the visible words", async () => {
    await mount();
    const [requested, withdraw] = Array.from(document.querySelectorAll("button"));
    expect(requested!.hasAttribute("aria-label")).toBe(false);
    expect(text(requested)).toBe(REQUESTED_COPY.requested);
    expect(withdraw!.hasAttribute("aria-label")).toBe(false);
    expect(text(withdraw)).toBe(REQUESTED_COPY.withdraw);
  });

  it("Withdraw calls DELETE /api/team-up/:id, is busy while it goes, hands over TeamUpSent, and focus moves to Team up", async () => {
    let release!: () => void;
    answer.wait = new Promise<void>((r) => (release = r));
    const log = await mount({ title: TITLE });
    const withdraw = document.querySelectorAll("button")[1]!;
    withdraw.focus();
    await act(async () => withdraw.click());
    expect(calls).toEqual([{ url: "/api/team-up/req-7", method: "DELETE" }]);
    expect(text(withdraw)).toBe("Withdrawing…");
    expect(withdraw.getAttribute("aria-busy")).toBe("true");
    // busy as every shared Button is busy: the quiet link keeps its look, with the spinner beside the words
    expect(withdraw.className).toBe("link-quiet");
    expect(withdraw.querySelector(".spin")?.getAttribute("aria-hidden")).toBe("true");
    await act(async () => withdraw.click()); // ignored while busy
    expect(calls.length).toBe(1);
    await act(async () => release());
    await settle();
    expect(log).toEqual([{ kind: "teamup", id: "req-7", ideaId: IDEA, note: "", brought: [], after: null }]);
    const teamUp = document.querySelector("button")!;
    expect(text(teamUp)).toBe("Team up");
    expect(document.activeElement).toBe(teamUp);
  });

  it("a draft's merge request withdraws the same way, with kind merge", async () => {
    const log = await mount({ kind: "merge", id: "mr-3" });
    await act(async () => document.querySelectorAll("button")[1]!.click());
    await settle();
    expect(calls).toEqual([{ url: "/api/team-up/mr-3", method: "DELETE" }]);
    expect(log[0]).toMatchObject({ kind: "merge", id: "mr-3", ideaId: IDEA });
  });

  it("a withdraw that fails says why and keeps Requested", async () => {
    answer = {
      status: 409,
      body: { error: { code: "not_waiting", message: "This request has already been answered." } },
    };
    const log = await mount({ title: TITLE });
    await act(async () => document.querySelectorAll("button")[1]!.click());
    await settle();
    expect(log).toEqual([]);
    expect(text(document.querySelector('[role="alert"]'))).toBe("This request has already been answered.");
    expect(text(document.querySelector("button"))).toBe("Requested");
  });

  it("a request with no id has nothing to withdraw (BLD-F074)", async () => {
    await mount({ id: "" });
    expect(Array.from(document.querySelectorAll("button")).map(text)).toEqual(["Requested"]);
  });
});

describe("RequestedAction, J-TEAMUP/3c, WCAG 2.4.3: focus reaches Team up whenever the frame comes (BLD-F105)", () => {
  it("a frame that comes before the host's redraw still finds Team up: the redraw is drawn before focus moves", async () => {
    // The frame runs the moment it is asked for, before React draws a change made after an await (J-TEAMUP/3c's race)
    const frame = vi.fn((cb: FrameRequestCallback) => {
      cb(0);
      return 1;
    });
    vi.stubGlobal("requestAnimationFrame", frame);
    await mount({ title: TITLE });
    const withdraw = document.querySelectorAll("button")[1]!;
    withdraw.focus();
    await act(async () => withdraw.click());
    await settle();
    const teamUp = document.querySelector("button")!;
    expect(text(teamUp)).toBe("Team up");
    expect(document.activeElement).toBe(teamUp);
    expect(frame).not.toHaveBeenCalled(); // focus moved at once; no frame was needed
  });

  it("a host that redraws later is looked for again on the next frame, as before", async () => {
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal(
      "requestAnimationFrame",
      vi.fn((cb: FrameRequestCallback) => frames.push(cb)),
    );
    await mount({ title: TITLE, redraw: "later" });
    const withdraw = document.querySelectorAll("button")[1]!;
    withdraw.focus();
    await act(async () => withdraw.click());
    await settle(); // the host has drawn "Team up" since; the frame has not come yet
    expect(frames.length).toBe(1);
    const teamUp = document.querySelector("button")!;
    expect(text(teamUp)).toBe("Team up");
    await act(async () => frames.splice(0).forEach((cb) => cb(0)));
    expect(document.activeElement).toBe(teamUp);
  });

  it("a host that keeps the pair keeps focus on Withdraw", async () => {
    const frame = vi.fn((cb: FrameRequestCallback) => {
      cb(0);
      return 1;
    });
    vi.stubGlobal("requestAnimationFrame", frame);
    const log = await mount({ title: TITLE, redraw: "never" });
    const withdraw = document.querySelectorAll("button")[1]!;
    withdraw.focus();
    await act(async () => withdraw.click());
    await settle();
    expect(log.length).toBe(1);
    expect(frame).toHaveBeenCalledTimes(1);
    expect(text(document.querySelector("button"))).toBe("Requested");
    expect(document.activeElement).toBe(withdraw);
  });
});
