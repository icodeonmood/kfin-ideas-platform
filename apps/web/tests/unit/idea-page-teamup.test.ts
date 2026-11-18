// @vitest-environment jsdom
/**
 * S-09's Team up card wired to lane F's C-SHEET-TEAMUP (S-09.states, S-09.rules/2; J-TEAMUP/1-3), with the sheet's
 * hook mocked: each state the API sends draws its own control, the crew alone gets the way into the conversation
 * (non-negotiable 7, P-PRODUCT.privacy), Withdraw on the page, and focus coming back to "Team up" (WCAG 2.4.3). Then
 * S-06's "You and the review desk" card as Status.md draws it: "Open the conversation" beside the heading and the
 * line about the review desk under it (BLD-E045), and the similar tiles' Team up. Copy: Idea.md, Status.md.
 * Synthetic people only: the pack's fictional cast (Ravi leads).
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
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

type Options = import("@/components/teamup/teamup-sheet").TeamUpSheetOptions;
const hook = vi.hoisted(() => ({
  open: vi.fn(),
  options: [] as unknown[],
}));
vi.mock("@/components/teamup/teamup-sheet", async (actual) => ({
  ...(await actual<typeof import("@/components/teamup/teamup-sheet")>()),
  useTeamUpSheet: (options: unknown) => {
    hook.options.push(options);
    return {
      open: hook.open,
      close: vi.fn(),
      isOpen: false,
      sheet: createElement("div", { "data-testid": "teamup-sheet" }),
    };
  },
}));

const { TeamUpCard } = await import("@/app/ideas/[id]/colleague-screen");
const { SharerScreen } = await import("@/app/ideas/[id]/sharer-screen");
type Words = Parameters<typeof TeamUpCard>[0]["t"];
type SharerProps = Parameters<typeof SharerScreen>[0];

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- Fixtures (synthetic) --------------------------------------------------------------------------------------
const IDEA = "IDEA-2026-001412";
const RAVI = { id: "p-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" };
const COUNT =
  "4 colleagues on it. Ravi leads it and decides who joins. The crew helps the review desk with detail and, if it’s picked, helps build it.";
const NOT_ASKED: Words = {
  state: "not_asked",
  count: 4,
  count_line: COUNT,
  faces: [RAVI],
  line: "Send Ravi a note about what you bring. Raised the same thing? Bring your idea along, and if Ravi approves, it joins this one with credit to you.",
  action: { label: "Team up", op: "teamup.open", sheet: "C-SHEET-TEAMUP" },
  can_team_up: true,
};
const SENT: Words = {
  state: "request_sent",
  count: 4,
  count_line: COUNT,
  faces: [RAVI],
  heading: "Waiting for Ravi",
  line: "Ravi reads your note and decides. You’ll hear in your Inbox.",
  action: { label: "Withdraw", op: "teamup.withdraw", request_id: "r-41" },
  can_team_up: false,
};
const ON_CREW: Words = {
  state: "on_crew",
  count: 5,
  count_line: COUNT.replace("4 colleagues", "5 colleagues"),
  faces: [RAVI],
  line: "You’re on the crew. You’ll get its updates.",
  action: { label: "Say hello", to: `/ideas/${IDEA}/conversation#say-hello` }, // BLD-F069
  can_team_up: false,
};
const CLOSED: Words = {
  state: "closed",
  count: 4,
  count_line: COUNT,
  line: "This idea isn’t going ahead, so it isn’t taking a crew.",
  can_team_up: false,
};
const MERGED: Words = {
  state: "merged",
  count: 4,
  count_line: COUNT,
  line: "This idea is now part of IDEA-2026-001398. Team up there.",
  link: { label: "Open IDEA-2026-001398", to: `/ideas/IDEA-2026-001398?from=${IDEA}` },
  can_team_up: false,
};

// --- Rendering --------------------------------------------------------------------------------------------------
let host: HTMLDivElement;
let root: Root | null = null;

function show(t: Words) {
  act(() => root!.render(createElement(TeamUpCard, { ideaId: IDEA, t })));
}
const q = <T extends Element = HTMLElement>(sel: string) => host.querySelector<T & HTMLElement>(sel);
const buttons = () => Array.from(host.querySelectorAll("button")).map((b) => b.textContent?.trim());
const links = () =>
  Array.from(host.querySelectorAll("a")).map((a) => [a.textContent, a.getAttribute("href")]);
const button = (name: string) =>
  Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((b) =>
    b.textContent?.trim().startsWith(name),
  );
const lastOptions = () => hook.options[hook.options.length - 1] as Options;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  hook.open.mockClear();
  hook.options.length = 0;
  refresh.mockClear();
});
afterEach(() => {
  act(() => root?.unmount());
  root = null;
  host.remove();
  vi.unstubAllGlobals();
});

describe("S-09.states: the Team up card draws what the API sends", () => {
  it("Not asked: Team up opens lane F's sheet on this idea, and the sheet is on the page", () => {
    show(NOT_ASKED);
    const team = button("Team up")!;
    expect(team.getAttribute("aria-haspopup")).toBe("dialog");
    expect(team.closest(".ip-dock")).not.toBeNull(); // S-09.rules/4: in the dock on a phone
    act(() => team.click());
    expect(hook.open).toHaveBeenCalledWith(IDEA);
    expect(q("[data-testid=teamup-sheet]")).not.toBeNull();
    expect(host.textContent).toContain(NOT_ASKED.line);
    expect(links()).toEqual([]); // no way into the conversation for someone not on the crew
  });

  it("a send and a withdraw in the sheet read the page again, so the card says what the API says", () => {
    show(NOT_ASKED);
    lastOptions().onSent?.({} as never);
    expect(refresh).toHaveBeenCalledTimes(1);
    lastOptions().onWithdrawn?.({} as never);
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it("Request sent: Waiting for Ravi with Withdraw, marked as the sheet's opener, then Ravi's line; no Team up", () => {
    show(SENT);
    const wait = q(".ip-team-wait")!;
    expect(wait.textContent).toContain("Waiting for Ravi");
    const withdraw = button("Withdraw")!;
    expect(wait.contains(withdraw)).toBe(true);
    expect(withdraw.getAttribute("data-teamup-opener")).toBe(IDEA); // focus comes back here (WCAG 2.4.3)
    expect(q("[role=status]")!.textContent).toBe(
      "Ravi reads your note and decides. You’ll hear in your Inbox.",
    );
    expect(buttons()).not.toContain("Team up");
    expect(links()).toEqual([]);
  });

  it("On the crew: Say hello goes to the conversation (S-08), cursor in the box (BLD-F069); no Team up", () => {
    show(ON_CREW);
    expect(links()).toEqual([["Say hello", `/ideas/${IDEA}/conversation#say-hello`]]);
    expect(q(".ip-team-line.ip-ok")!.textContent).toBe("You’re on the crew. You’ll get its updates.");
    expect(buttons()).toEqual([]);
  });

  it("the conversation link is the crew's alone: a link in any other state is not drawn", () => {
    for (const t of [NOT_ASKED, SENT, CLOSED]) {
      show({ ...t, action: { ...(t.action ?? { label: "Say hello" }), to: `/ideas/${IDEA}/conversation` } });
      expect(host.querySelector('a[href$="/conversation"]')).toBeNull();
    }
  });

  it("S-09.rules/2: closed is one line and nothing to press; merged adds the link to the surviving idea", () => {
    show(CLOSED);
    expect(q("[role=status]")!.textContent).toBe(CLOSED.line);
    expect(buttons()).toEqual([]);
    expect(links()).toEqual([]);
    show(MERGED);
    expect(q("[role=status]")!.textContent).toBe(MERGED.line);
    expect(buttons()).toEqual([]);
    expect(links()).toEqual([["Open IDEA-2026-001398", `/ideas/IDEA-2026-001398?from=${IDEA}`]]);
  });

  it("a Team up the API does not allow is not drawn, whatever the action says", () => {
    show({ ...NOT_ASKED, can_team_up: false });
    expect(buttons()).toEqual([]);
  });
});

describe("S-09 Withdraw on the page (J-TEAMUP/3, L-TEAMUP.rules/3)", () => {
  const refused = (status: number, message: string) =>
    vi.fn(async () => new Response(JSON.stringify({ error: { code: "x", message } }), { status }));
  const press = async (name: string) => {
    await act(async () => {
      button(name)!.click();
    });
  };

  it("withdraws the request, reads the page again, and puts focus on Team up when it comes back", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    show(SENT);
    await press("Withdraw");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/team-up/r-41",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(refresh).toHaveBeenCalledTimes(1);
    show(NOT_ASKED); // the refreshed page
    expect(document.activeElement).toBe(button("Team up"));
  });

  it("after a withdraw that worked, Withdraw stays busy until the page has its new state: no second DELETE", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    show(SENT);
    await press("Withdraw");
    // The refresh has not landed: the same request is still on the page
    show(SENT);
    expect(button("Withdraw")!.getAttribute("aria-busy")).toBe("true");
    await press("Withdraw");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(q("[role=alert]")).toBeNull();
  });

  it("a withdraw refused because the lead answered first (409) keeps the API's message and reads the card again", async () => {
    const message = "That request has already been answered.";
    vi.stubGlobal("fetch", refused(409, message));
    show(SENT);
    await press("Withdraw");
    expect(q("[role=alert]")!.textContent).toContain(message);
    expect(refresh).toHaveBeenCalledTimes(1);
    // The lead had approved: the card says so, the message stays, focus goes to the card's heading (no Team up)
    show(ON_CREW);
    expect(q("[role=alert]")!.textContent).toContain(message);
    expect(document.activeElement).toBe(q("#ip-team-h"));
  });

  it("a request already gone (404) reads the card again too", async () => {
    vi.stubGlobal("fetch", refused(404, "We couldn’t find that."));
    show(SENT);
    await press("Withdraw");
    expect(q("[role=alert]")!.textContent).toContain("We couldn’t find that.");
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("any other refusal keeps the card and Withdraw, says so, and does not read the page again", async () => {
    vi.stubGlobal("fetch", refused(500, "Something went wrong. Please try again."));
    show(SENT);
    await press("Withdraw");
    expect(q("[role=alert]")!.textContent).toContain("Something went wrong. Please try again.");
    expect(button("Withdraw")!.getAttribute("aria-busy")).toBeNull();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("offline: the sheet's line, and Withdraw can be pressed again", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("network");
      }),
    );
    show(SENT);
    await press("Withdraw");
    expect(q("[role=alert]")!.textContent).toContain("Check your connection, then try again.");
    expect(button("Withdraw")!.getAttribute("aria-busy")).toBeNull();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("withdrawn from the sheet, focus also lands on Team up once the page has it again", () => {
    show(SENT);
    act(() => lastOptions().onWithdrawn?.({} as never));
    show(NOT_ASKED);
    expect(document.activeElement).toBe(button("Team up"));
  });

  it("withdrawn from the sheet before its send was read back, focus waits for the page that has Team up", () => {
    show(NOT_ASKED);
    act(() => lastOptions().onWithdrawn?.({} as never));
    show(SENT); // the send's own page read
    expect(document.activeElement).not.toBe(button("Withdraw"));
    show(NOT_ASKED); // the withdraw's
    expect(document.activeElement).toBe(button("Team up"));
  });
});

// --- S-06 -------------------------------------------------------------------------------------------------------
const TILE = {
  idea: {
    id: IDEA,
    title: "Rejection SMS codes confuse investors",
    status: "with_review_desk",
    area: "Investor service",
    city: "Hyderabad",
    shared_at: null,
    lead: RAVI,
    crew_faces: [RAVI],
    crew_count: 4,
    in_their_words: "A synthetic short summary.",
  },
  strength: "close",
  reason: "Close match: same SMS, same calls",
  meta: `${IDEA}, Investor service, Hyderabad`,
  pill: { status: "with_review_desk", label: "With the review desk", variant: "blue" },
  count_line: "4 colleagues on it",
  my_state: "none",
  to: `/ideas/${IDEA}?from=IDEA-2026-001481`,
  actions: [
    { label: "Preview", op: "preview", accessible_name: "Preview Rejection SMS codes confuse investors" },
    { label: "Team up", op: "team_up", accessible_name: "Team up on Rejection SMS codes confuse investors" },
  ],
};
const OPENED_LINE =
  "The review desk opened it on Monday 16 November, so the idea itself can’t be changed now. Write to them in the conversation.";
const DECIDED_LINE =
  "The review desk has decided. The full conversation, with every answer, is one tap away.";

function sharer(
  state: string,
  conversation: Record<string, unknown>,
  window: Record<string, unknown> | null,
) {
  return {
    view: {
      view: "sharer",
      screen: "S-06",
      idea: {
        id: "IDEA-2026-001481",
        ref: "IDEA-2026-001481",
        title: "Investors call to ask why a redemption was rejected",
        status: "with_review_desk",
        stages: [],
        own_words: [],
        hidden: [],
        files: [],
        has_open_questions: false,
        kept_separate: false,
      },
      page: {
        state,
        state_label: "",
        pill: { status: "with_review_desk", label: "With the review desk", variant: "blue" },
        breadcrumb: { label: "My ideas", to: "/my-ideas", current: "IDEA-2026-001481" },
        shared_label: null,
        first_arrival: false,
        card: { lead: "Sent. The review desk has your answers.", rest: "" },
        window,
        actions: { conversation: conversation.link },
        lane_b: { question_set: "", decision: "" },
        shared: {
          intro: "",
          rows: [],
          hidden: { chips: [], more: 0, note: "", all: [] },
          attached: { label: "Attached", files: [], answers: [] },
          fix: { label: "Your fix", answers: [] },
        },
        conversation,
        similar: {
          heading: "Colleagues on something similar",
          intro:
            "Matched when you shared. Team up to ask to join their crew, and bring this idea along if you like.",
          tiles: [TILE],
        },
        merged: null,
        own_words_unmasked: false,
      },
    },
    decision: null,
    questions: null,
    partFailed: false,
  } as unknown as SharerProps;
}
const LINK = { label: "Open the conversation", to: "/ideas/IDEA-2026-001481/conversation" };

function conversationCard(html: string): string {
  const at = html.indexOf('aria-labelledby="ip-conv-h"');
  expect(at).toBeGreaterThan(-1);
  return html.slice(at, html.indexOf("</section>", at));
}

describe("S-06: You and the review desk as Status.md draws it (BLD-E045)", () => {
  it("answers sent: the heading with Open the conversation beside it, then the desk's line, said once on the page", () => {
    const html = renderToStaticMarkup(
      createElement(
        SharerScreen,
        sharer(
          "answers_sent",
          { heading: "You and the review desk", count: 3, link: LINK },
          {
            open: false,
            line: OPENED_LINE,
          },
        ),
      ),
    );
    const card = conversationCard(html);
    expect(card).toMatch(
      /<div class="ip-conv-head"><h2 id="ip-conv-h"[^>]*>You and the review desk<\/h2><a (?=[^>]*class="tb")[^>]*href="\/ideas\/IDEA-2026-001481\/conversation"[^>]*>Open the conversation<\/a><\/div><p class="ip-side-l">The review desk opened it on Monday 16 November/,
    );
    expect(html.split("The review desk opened it on").length - 1).toBe(1);
    expect(html).not.toContain('class="ip-window"');
  });

  it("decided: the decided line under the link", () => {
    const html = renderToStaticMarkup(
      createElement(
        SharerScreen,
        sharer(
          "picked",
          { heading: "You and the review desk", count: 3, link: LINK, sub_line: DECIDED_LINE },
          null,
        ),
      ),
    );
    expect(conversationCard(html)).toContain(
      `Open the conversation</a></div><p class="ip-side-l">${DECIDED_LINE}</p>`,
    );
  });

  const PICKED =
    "Picked. A clear problem, a real number and a simple fix. We’ve joined it with IDEA-2026-001412, which found the same calls in Hyderabad, so one team builds one fix.";
  const decisionMessage = (from: Record<string, string>, fromLabel: string) => ({
    id: "decision-d1",
    kind: "decision",
    from,
    from_label: fromLabel,
    at: "2026-11-16T11:28:00Z",
    at_label: "Monday 16 November, 4:58 pm",
    by_line: `${fromLabel}, Monday 16 November, 4:58 pm`,
    text: PICKED,
  });

  it("S-06.layout/8 BLD-E058 DEC-111 (J-TRACK/7): decided, the desk's message ends the card, from the review desk with no face and no empty line", () => {
    const desk = { id: "", name: "The review desk", first_name: "The review desk", initials: "" };
    const html = renderToStaticMarkup(
      createElement(
        SharerScreen,
        sharer(
          "picked",
          {
            heading: "You and the review desk",
            count: 1,
            link: LINK,
            sub_line: DECIDED_LINE,
            messages: [decisionMessage(desk, "The review desk")],
          },
          null,
        ),
      ),
    );
    const card = conversationCard(html);
    expect(card).toContain(
      `<p class="ip-side-l">${DECIDED_LINE}</p><ol class="ip-msgs"><li class="ip-msg dec no-face"><p class="ip-msg-h"><b>The review desk</b>, Monday 16 November, 4:58 pm</p><p class="ip-msg-b">${PICKED}</p></li></ol>`,
    );
    expect(card).not.toContain("No messages yet");
    expect(card).not.toContain('class="av');
  });

  it("S-06.layout/8 BLD-E058 DEC-111: a sharer on the review desk reads who decided, with her initials, as Status.md draws Meera", () => {
    const meera = {
      id: "u-meera",
      name: "Meera Iyer",
      first_name: "Meera",
      initials: "MI",
      role_label: "from the review desk",
    };
    const html = renderToStaticMarkup(
      createElement(
        SharerScreen,
        sharer(
          "picked",
          {
            heading: "You and the review desk",
            count: 1,
            link: LINK,
            sub_line: DECIDED_LINE,
            messages: [decisionMessage(meera, "Meera from the review desk")],
          },
          null,
        ),
      ),
    );
    const card = conversationCard(html);
    expect(card).toMatch(
      /<li class="ip-msg dec"><span class="av av-32"[^>]*aria-hidden="true"[^>]*>MI<\/span><p class="ip-msg-h"><b>Meera from the review desk<\/b>, Monday 16 November, 4:58 pm<\/p>/,
    );
    expect(card).toContain(`<p class="ip-msg-b">${PICKED}</p>`);
  });

  it("S-06.layout/8 BLD-E058 L-COMMITTEE (Reversed by the Ones Committee): the desk's message stays, then the committee member's, its face in ink, under the committee's line", () => {
    const desk = { id: "", name: "The review desk", first_name: "The review desk", initials: "" };
    const rohan = {
      id: "u-rohan",
      name: "Rohan Mehta",
      first_name: "Rohan",
      initials: "RM",
      role_label: "from the Ones Committee",
    };
    const note =
      "We’ve moved it to not now: the SMS templates are frozen until January. It comes back first in February.";
    const committeeLine =
      "The Ones Committee has the last word on this decision. The full conversation is one tap away.";
    const html = renderToStaticMarkup(
      createElement(
        SharerScreen,
        sharer(
          "being_built",
          {
            heading: "You and the review desk",
            count: 2,
            link: LINK,
            sub_line: committeeLine,
            messages: [
              decisionMessage(desk, "The review desk"),
              {
                id: "reversal-r1",
                kind: "reversal",
                from: rohan,
                from_label: "Rohan Mehta from the Ones Committee",
                at: "2026-11-24T12:10:00Z",
                at_label: "Tuesday 24 November, 5:40 pm",
                by_line: "Rohan Mehta from the Ones Committee, Tuesday 24 November, 5:40 pm",
                text: note,
              },
            ],
          },
          null,
        ),
      ),
    );
    const card = conversationCard(html);
    expect(card).toContain(`<p class="ip-side-l">${committeeLine}</p><ol class="ip-msgs">`);
    expect(card).not.toContain(DECIDED_LINE);
    expect(card).toMatch(
      new RegExp(
        `<li class="ip-msg dec no-face"><p class="ip-msg-h"><b>The review desk</b>, Monday 16 November, 4:58 pm</p><p class="ip-msg-b">${PICKED}</p></li>` +
          `<li class="ip-msg dec oc"><span class="av av-32"[^>]*>RM</span><p class="ip-msg-h"><b>Rohan Mehta from the Ones Committee</b>, Tuesday 24 November, 5:40 pm</p><p class="ip-msg-b">${note}</p></li></ol>`,
      ),
    );
  });

  it("just shared: the link, the empty line, and the open window stays under the track", () => {
    const empty =
      "No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we tell you on Teams.";
    const html = renderToStaticMarkup(
      createElement(
        SharerScreen,
        sharer(
          "just_shared",
          { heading: "You and the review desk", count: 0, link: LINK, empty_line: empty },
          {
            open: true,
            line: "Open to changes until Tuesday 17 November. Edit or withdraw it any time before the review desk opens it.",
          },
        ),
      ),
    );
    const card = conversationCard(html);
    expect(card).toContain(">Open the conversation</a>");
    expect(card).toContain(empty);
    expect(card).not.toContain("Open to changes");
    expect(html).toContain('class="ip-window is-open"');
  });

  it("the similar tiles' Team up opens lane F's sheet on that idea (C-SIMGRID)", () => {
    act(() =>
      root!.render(
        createElement(SharerScreen, sharer("just_shared", { heading: "x", count: 0, link: LINK }, null)),
      ),
    );
    const team = Array.from(host.querySelectorAll("button")).find(
      (b) => b.getAttribute("aria-label") === "Team up on Rejection SMS codes confuse investors",
    )!;
    expect(team.getAttribute("aria-haspopup")).toBe("dialog");
    act(() => team.click());
    expect(hook.open).toHaveBeenCalledWith(IDEA);
    expect(q("[data-testid=teamup-sheet]")).not.toBeNull();
  });
});

describe("S-06: similar tiles on a crew you are already in, and a part left empty (BLD-E056, BLD-E057)", () => {
  const ON_CREW = {
    ...TILE,
    my_state: "on_crew",
    actions: [TILE.actions[0]],
    done_line: "On the crew",
  };
  function withTiles(tiles: unknown[], rows: unknown[] = []): SharerProps {
    const props = sharer("just_shared", { heading: "x", count: 0, link: LINK }, null);
    const page = (props.view as unknown as { page: Record<string, Record<string, unknown>> }).page;
    page.similar = { ...page.similar, tiles };
    page.shared = { ...page.shared, rows };
    return props;
  }

  it("C-SIMGRID.tile J-SIMILAR/7, J-REVIEW/M3: on its crew, the row says On the crew and offers no Team up", () => {
    act(() => root!.render(createElement(SharerScreen, withTiles([ON_CREW]))));
    const row = q(".ip-tile-a")!;
    expect(row.querySelector(".ip-tile-done")?.textContent).toBe("On the crew");
    const labels = Array.from(row.querySelectorAll("button")).map((b) => b.textContent);
    expect(labels).toEqual(["Preview"]);
    expect(buttons().some((b) => b?.startsWith("Team up"))).toBe(false);
  });

  it("C-SIMGRID.tile: a tile the payload offers Team up on keeps it, and no On the crew line", () => {
    act(() => root!.render(createElement(SharerScreen, withTiles([TILE]))));
    const row = q(".ip-tile-a")!;
    expect(Array.from(row.querySelectorAll("button")).map((b) => b.textContent)).toEqual([
      "Preview",
      "Team up",
    ]);
    expect(row.querySelector(".ip-tile-done")).toBeNull();
  });

  it("S-06.layout/5 J-REVIEW/1, J-TRACK/7: an empty How often reads Not given., as S-R2 reads it", () => {
    const html = renderToStaticMarkup(
      createElement(
        SharerScreen,
        withTiles(
          [],
          [
            { part: "often", label: "How often", value: "", empty_line: "Not given.", answers: [] },
            { part: "area", label: "Area", value: "Operations" },
          ],
        ),
      ),
    );
    expect(html).toContain('<dt>How often</dt><dd><p class="ip-val ip-mute">Not given.</p>');
    expect(html).toContain('<dt>Area</dt><dd><p class="ip-val">Operations</p>');
  });
});
