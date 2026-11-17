// @vitest-environment jsdom
/**
 * S-H2B inside C-INBOX-READER against lane F's `GET /api/team-up/:id` on f/teamup-4 (BLD-F015, BLD-F022, BLD-F024):
 * (a) a brought item lane F shrank to `{id, title: "", status}` is not shown, and with nothing brought there is no
 * card, no heading, the no-idea explanation and no Merge button; (b) a 404 says "We couldn’t find that." with no
 * retry; (c) a request that is not waiting shows its ended line; (d) a 409 `not_waiting` answer ends it in place;
 * (e) focus never drops to the page (WCAG 2.4.3, BLD-A195): Decline moves it to the reason field, Back returns it to
 * Decline, a sent answer moves it to the result line, and an answer that could not be sent returns it to the button.
 * Fixtures are synthetic people in lane F's shape.
 */
import { act, createElement, Fragment } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  answerButtons,
  answerOf,
  endedLine,
  loadFailure,
  readRequest,
  refusedAnswer,
  RequestBody,
  useRequest,
  type Request,
} from "@/app/inbox/teamup-request";
import type { Action, InboxEntry } from "@/server/inbox";

vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const RID = "5b0e7a3c-2d41-4f6e-9a18-0c7d3e2b9f11";

/** Lane F's lead view of a merge request with one idea brought, waiting (f/teamup-4 `read`). */
function laneF(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: RID,
    request: "merge",
    idea_id: "IDEA-2026-000900",
    from: { id: "u-kavya", name: "Kavya Menon", first_name: "Kavya" },
    note: "I take these calls at our branch every day, about 40 a day.",
    brought: [
      {
        id: "IDEA-2026-000901",
        title: "Investors call to ask why a redemption was rejected",
        status: "with_review_desk",
        summary: "About 40 investors a day call the branch.",
        byline: "Kavya Menon, Investor service. Shared today.",
      },
    ],
    state: "sent",
    sent_at: "2026-11-17T10:00:00+05:30",
    reader: {
      kind: "Merge request",
      line: "Kavya Menon asks to team up and merge their idea into yours",
      note_heading: "Kavya’s note",
      brought_heading: "The idea Kavya asks you to merge into yours",
      open_label: "Open Kavya’s idea",
      explain:
        "Merge it, and Kavya’s idea joins yours: they are on your crew and credited on it. Team up only puts Kavya on your crew and keeps their idea separate. Decline, and they send theirs on its own, with your reason if you give one.",
    },
    answers: [
      { answer: "decline", label: "Decline", style: "text" },
      { answer: "team_only", label: "Team up only", style: "line" },
      { answer: "merge", label: "Merge it", style: "primary" },
    ],
    ...over,
  };
}

/** The lead's Inbox item's answers, as lane F registers them (bare ops, BLD-A188). */
const OPS: Action[] = [
  { label: "Decline", style: "text", op: "decline" },
  { label: "Team up only", style: "line", op: "team_only" },
  { label: "Merge it", style: "primary", op: "merge" },
];

function body(req: Request | null, extra: Partial<Parameters<typeof RequestBody>[0]> = {}): string {
  const shown = req ? endedLine(req, "Kavya") : null;
  return renderToStaticMarkup(
    createElement(RequestBody, {
      req,
      failure: "",
      first: "Kavya",
      waiting: req?.state === "sent" && !shown,
      shown,
      declining: false,
      reason: "",
      onReason: () => undefined,
      error: "",
      ...extra,
    }),
  );
}

describe("S-H2B in the Inbox reader, against lane F's GET /api/team-up/:id", () => {
  it("S-H2B.reader: a waiting merge request reads lane F's words and offers the three answers in order", () => {
    const req = readRequest(laneF(), RID);
    expect(req.brought).toHaveLength(1);
    const html = body(req);
    expect(html).toContain("Kavya’s note");
    expect(html).toContain("The idea Kavya asks you to merge into yours");
    expect(html).toContain("Open Kavya’s idea");
    expect(html).toContain("Merge it, and Kavya’s idea joins yours");
    expect(answerButtons(OPS, true).map((b) => [b.answer, b.label, b.style])).toEqual([
      ["decline", "Decline", "text"],
      ["team_only", "Team up only", "line"],
      ["merge", "Merge it", "primary"],
    ]);
    expect(answerOf("teamup.answer.merge")).toBe("merge"); // lane F's older op name still reads
  });

  it("S-H2B.rules/3 BLD-F022 (a): a shrunken brought item is dropped; nothing brought means no card, no heading, the no-idea explanation and no Merge", () => {
    // The sharer withdrew the brought idea while the request waits: lane F gives its reference and status only.
    const req = readRequest(
      laneF({ brought: [{ id: "IDEA-2026-000901", title: "", status: "withdrawn" }] }),
      RID,
    );
    expect(req.brought).toEqual([]);
    expect(req.listed).toBe(1);
    const html = body(req);
    expect(html).not.toContain("ibx-card");
    expect(html).not.toContain("asks you to merge into yours");
    expect(html).not.toContain("Open Kavya’s idea");
    expect(html).not.toContain("Merge it");
    expect(html).toContain("Kavya’s note");
    expect(html).toContain(
      "Approve, and Kavya joins your crew. Decline, and they see your reason if you give one.",
    );
    expect(answerButtons(OPS, false).map((b) => [b.answer, b.label, b.style])).toEqual([
      ["decline", "Decline", "text"],
      ["team_only", "Approve", "primary"],
    ]);
  });

  it("S-H2B.reader (a): a team-up with nothing brought uses lane F's own no-idea words", () => {
    const req = readRequest(
      laneF({
        request: "teamup",
        brought: [],
        reader: {
          kind: "Team-up request",
          line: "Kavya Menon asks to team up",
          note_heading: "Kavya’s note",
          explain: "Approve, and Kavya joins your crew. Decline, and they see your reason if you give one.",
        },
      }),
      RID,
    );
    const html = body(req);
    expect(html).not.toContain("ibx-card");
    expect(html).toContain("Approve, and Kavya joins your crew.");
  });

  it("A-API.team-up BLD-F025 (b): a 404 shows lane F's message and no retry; anything else asks to try again", () => {
    const notFound = loadFailure(404, { error: { code: "not_found", message: "We couldn’t find that." } });
    expect(notFound).toBe("We couldn’t find that.");
    expect(loadFailure(404, { error: { code: "not_found" } })).toBe("We couldn’t find that.");
    // A 404 with no error of lane F's is the route not being there yet: try again later (BLD-A208).
    expect(loadFailure(404, null)).toBe("We can't show this request just now. Please try again in a minute.");
    const html = body(null, { failure: notFound });
    expect(html).toContain("We couldn’t find that.");
    expect(html).not.toMatch(/try again/i);
    expect(loadFailure(503, null)).toBe("We can't show this request just now. Please try again in a minute.");
  });

  it("S-H2B.states (c): a request that is not waiting shows its ended line, and no answers or explanation", () => {
    // A draft merge request that ended: lane F shrinks the draft and sends no answers (BLD-F022, BLD-F024).
    const withdrawn = readRequest(
      laneF({ state: "withdrawn", brought: [{ id: "d-1", title: "", status: "draft" }], answers: [] }),
      RID,
    );
    expect(endedLine(withdrawn, "Kavya")).toEqual({
      state: "withdrawn",
      text: "Kavya withdrew this request.",
    });
    const html = body(withdrawn);
    expect(html).toContain("Kavya withdrew this request.");
    expect(html).not.toContain("Merge it, and");
    expect(html).not.toContain("ibx-card");

    const closed = readRequest(laneF({ state: "closed", answers: [] }), RID);
    expect(endedLine(closed, "Kavya")?.text).toBe("This idea is no longer open to team up.");

    // Answered: lane F's result line wins (S-H2B.states), with "Say hello to Kavya" after an approval.
    const merged = readRequest(
      laneF({
        state: "approved_merged",
        result: {
          state: "merged",
          text: "Merged. Kavya’s idea is now part of yours, and they are on your crew, credited. We’ve told them.",
        },
        say_hello: { label: "Say hello to Kavya", to: "/ideas/IDEA-2026-000900/conversation" },
      }),
      RID,
    );
    expect(endedLine(merged, "Kavya")).toMatchObject({
      state: "merged",
      sayHello: { label: "Say hello to Kavya", to: "/ideas/IDEA-2026-000900/conversation" },
    });
    // No result line in the response: CrewRequest.md's lines in BLD-E008's words.
    const declined = readRequest(laneF({ state: "declined", lead_reason: "The crew is full for now" }), RID);
    expect(endedLine(declined, "Kavya")?.text).toBe(
      "Declined. Kavya sees your reason: “The crew is full for now”. They can send theirs on its own.",
    );
    const teamed = readRequest(laneF({ state: "approved_team_only" }), RID);
    expect(endedLine(teamed, "Kavya")?.text).toBe(
      "Teamed up. Kavya is on your crew. Their idea stays separate, and they send it on its own. We’ve told them.",
    );
    expect(endedLine(readRequest(laneF(), RID), "Kavya")).toBeNull(); // waiting: no line
  });

  it("BLD-F024 (d): a 409 not_waiting on answering ends the request in place as withdrawn, with lane F's line", () => {
    const refused = refusedAnswer(
      409,
      { error: { code: "not_waiting", message: "Kavya withdrew this request." } },
      "Kavya",
    );
    expect(refused).toEqual({ ended: { state: "withdrawn", text: "Kavya withdrew this request." } });
    expect(refusedAnswer(409, { error: { code: "idea_closed" } }, "Kavya")).toEqual({
      ended: { state: "closed", text: "This idea is no longer open to team up." },
    });
    expect(refusedAnswer(500, null, "Kavya")).toEqual({
      error: "We couldn't send that just now. Please try again in a minute.",
    });
    // What the reader shows once it has ended: the line, no explanation, nothing brought.
    const req = { ...readRequest(laneF(), RID), state: "withdrawn", brought: [] };
    const html = body(req, { shown: "ended" in refused ? refused.ended : null, waiting: false });
    expect(html).toContain("Kavya withdrew this request.");
    expect(html).not.toContain("Merge it, and");
    expect(html).not.toContain("ibx-card");
  });
});

/** The lead's Inbox item for the waiting merge request (as the worker renders it). */
const ITEM: InboxEntry = {
  id: "41",
  kind: "teamup_request",
  from: { id: "u-kavya", name: "Kavya Menon", first_name: "Kavya", initials: "KM" },
  idea: {
    id: "IDEA-2026-000900",
    title: "Rejection SMS codes confuse investors",
    status: "with_review_desk",
  },
  line: "asks to team up and merge their idea into yours",
  at: "2026-11-18T10:00:00+05:30",
  unread: false,
  needs_you: true,
  archived: false,
  body: { heading: "Merge request", note: "", sender: "Kavya Menon", request_id: RID },
  actions: OPS,
} as InboxEntry;

/** The request as the reader shows it: its body, then its bar, as C-INBOX-READER lays them out. */
function Harness() {
  const view = useRequest(
    ITEM,
    () => undefined,
    () => undefined,
  );
  return view ? createElement(Fragment, null, view.body, view.bar) : null;
}

describe("S-H2B focus in the Inbox reader (WCAG 2.4.3)", () => {
  let host: HTMLElement;
  let root: Root;
  let answer: () => Response;

  function json(status: number, data: unknown): Response {
    return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
  }

  beforeEach(() => {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    answer = () =>
      json(200, {
        result: { state: "declined", text: "Declined. We’ve told Kavya. They can send theirs on its own." },
      });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === `/api/team-up/${RID}`) return json(200, laneF());
        if (url === `/api/team-up/${RID}/answer`) {
          // The answers are disabled while it is sent; a browser then moves focus off the pressed button to the
          // page (the focus fixup rule), which jsdom does not do by itself.
          (document.activeElement as HTMLElement | null)?.blur();
          return answer();
        }
        return json(404, { error: { code: "not_found", message: "We couldn’t find that." } });
      }),
    );
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
  });

  async function settle() {
    for (let i = 0; i < 6; i++) await act(async () => await Promise.resolve());
  }

  async function open() {
    await act(async () => root.render(createElement(Harness)));
    await settle();
  }

  function button(name: string): HTMLButtonElement {
    const found = Array.from(host.querySelectorAll("button")).find((b) => b.textContent?.trim() === name);
    if (!found) throw new Error(`no button ${name}`);
    return found;
  }

  async function press(name: string) {
    const b = button(name);
    b.focus();
    await act(async () => b.click());
    await settle();
  }

  it("S-H2B.rules/1: Decline moves focus to the reason field, and Back returns it to Decline", async () => {
    await open();
    await press("Decline");
    const field = host.querySelector<HTMLTextAreaElement>("#ibx-reason");
    expect(field).not.toBeNull();
    expect(document.activeElement).toBe(field);

    await press("Back");
    expect(host.querySelector("#ibx-reason")).toBeNull();
    expect(document.activeElement).toBe(button("Decline"));
  });

  it("S-H2B.rules/2: once a decline is sent, focus is on the result line, which can take it", async () => {
    await open();
    await press("Decline");
    await press("Decline the request");
    const result = host.querySelector<HTMLParagraphElement>(".ibx-result");
    expect(result?.textContent).toBe("Declined. We’ve told Kavya. They can send theirs on its own.");
    expect(result?.tabIndex).toBe(-1);
    expect(document.activeElement).toBe(result);
  });

  it("S-H2B.rules/2: Merge it sent, or ended in place by a 409, also puts focus on the result line", async () => {
    answer = () =>
      json(200, {
        result: {
          state: "merged",
          text: "Merged. Kavya’s idea is now part of yours, and they are on your crew, credited. We’ve told them.",
        },
        say_hello: { label: "Say hello to Kavya", to: "/ideas/IDEA-2026-000900/conversation" },
      });
    await open();
    await press("Merge it");
    expect(document.activeElement).toBe(host.querySelector(".ibx-result"));
    expect(document.activeElement?.textContent).toMatch(/^Merged\. /);

    await act(async () => root.unmount());
    root = createRoot(host);
    answer = () => json(409, { error: { code: "not_waiting", message: "Kavya withdrew this request." } });
    await open();
    await press("Team up only");
    expect(document.activeElement).toBe(host.querySelector(".ibx-result"));
    expect(document.activeElement?.textContent).toBe("Kavya withdrew this request.");
  });

  it("S-H2B.rules/2: an answer that could not be sent keeps focus on the button pressed, with the error shown", async () => {
    answer = () => json(500, null);
    await open();
    await press("Merge it");
    expect(host.querySelector('[role="alert"]')?.textContent).toBe(
      "We couldn't send that just now. Please try again in a minute.",
    );
    expect(document.activeElement).toBe(button("Merge it"));
  });
});
