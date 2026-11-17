/**
 * S-H2B inside C-INBOX-READER against lane F's `GET /api/team-up/:id` on f/teamup-4 (BLD-F015, BLD-F022, BLD-F024):
 * (a) a brought item lane F shrank to `{id, title: "", status}` is not shown, and with nothing brought there is no
 * card, no heading, the no-idea explanation and no Merge button; (b) a 404 says "We couldn’t find that." with no
 * retry; (c) a request that is not waiting shows its ended line; (d) a 409 `not_waiting` answer ends it in place.
 * Fixtures are synthetic people in lane F's shape.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  answerButtons,
  answerOf,
  endedLine,
  loadFailure,
  readRequest,
  refusedAnswer,
  RequestBody,
  type Request,
} from "@/app/inbox/teamup-request";
import type { Action } from "@/server/inbox";

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
    expect(loadFailure(404, null)).toBe("We couldn’t find that.");
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
