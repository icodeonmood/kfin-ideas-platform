// @vitest-environment jsdom
/**
 * V-ACC.teamup gap tests on the web (J-TEAMUP), from lane F's coverage map of 18 Nov 10:00. Each test names its row.
 * They exercise other lanes' screens and components as they are on main, and change none of them:
 * - /4 "Waiting for Ravi" with Withdraw on every screen that shows the idea: S-09's Team up card (lane E), S-05's
 *   similar tile and its preview (lane C), and the opener after lane F's sheet (C-SHEET-TEAMUP.after);
 * - /6 no Undo after any of the lead's three answers on S-H2B (lane A's reader);
 * - /7 Find your crew's Next lifts the front card out to the right and tucks it behind the pile (lane D's Deck);
 * - /9 Home's Ones: one card per wheel step, and the page scrolls on at either end (lane D's fan).
 * Synthetic people only: the pack's fictional cast (Kavya asks, Ravi leads).
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { act, createElement, Fragment, useState, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { InboxEntry } from "@/server/inbox";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), replace: vi.fn(), push: vi.fn() }),
  useParams: () => ({ id: "IDEA-2026-001412" }),
  usePathname: () => "/ideas/IDEA-2026-001412",
}));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: ({ href, children, ...rest }: { href: string; children?: ReactNode }) =>
      h("a", { href, ...rest }, children),
  };
});
vi.mock("@/lib/motion/spark", () => ({ sparkBurst: vi.fn() }));

const { TeamUpCard } = await import("@/app/ideas/[id]/colleague-screen");
const { SimilarGrid } = await import("@/app/share/[id]/check/similar");
const { TeamUpSheet } = await import("@/components/teamup/teamup-sheet");
const { useRequest } = await import("@/app/inbox/teamup-request");
const { Deck } = await import("@/components/ui/deck");
const { OnesFan } = await import("@/components/ui/ones-fan");
type CardWords = Parameters<typeof TeamUpCard>[0]["t"];
type Sent = import("@/components/teamup/teamup-sheet").TeamUpSent;
type Match = import("@/lib/contracts").SimilarMatch;

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- One request, waiting on Ravi (synthetic) ------------------------------------------------------------------
const IDEA = "IDEA-2026-001412";
const TITLE = "Rejection SMS codes confuse investors";
const RID = "5b0e7a3c-2d41-4f6e-9a18-0c7d3e2b9f11";
const RAVI = { id: "u-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" };
const KAVYA = { id: "u-kavya", name: "Kavya Menon", first_name: "Kavya", initials: "KM" };
const NOTE =
  "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07. I can bring the call log.";
/** The request as A-API.team-up returns it (E-ENTITIES TeamUpRequest, state `sent`). */
const REQUEST = {
  id: RID,
  idea_id: IDEA,
  from: KAVYA,
  note: NOTE,
  brought: [],
  state: "sent" as const,
  sent_at: "2026-11-18T10:30:00+05:30",
};
/** What the worker sends each screen for that one request (`teamup/rules.py requester_after`, `ideapage/colleague.py`). */
const AFTER = {
  state: "waiting",
  line: "Waiting for Ravi",
  detail: "Ravi reads your note, then approves or declines. You’ll hear in your Inbox.",
  action: { label: "Withdraw", op: "withdraw" },
};
const S09: CardWords = {
  state: "request_sent",
  count: 4,
  count_line: "4 colleagues on it. Ravi leads it and decides who joins.",
  faces: [RAVI],
  heading: "Waiting for Ravi",
  line: "Ravi reads your note and decides. You’ll hear in your Inbox.",
  action: { label: "Withdraw", op: "teamup.withdraw", request_id: RID },
  can_team_up: false,
};
const MATCH: Match = {
  idea: {
    id: IDEA,
    title: TITLE,
    status: "with_review_desk",
    area: "Investor service",
    city: "Hyderabad",
    shared_at: "2026-11-09T10:00:00+05:30",
    lead: RAVI,
    crew_faces: [RAVI],
    crew_count: 4,
    in_their_words: "Investors get a code, not a reason, and then they call us.",
    hue: 1,
  },
  strength: "close",
  reason: "Close match: same SMS, same calls",
  my_request: REQUEST,
} as Match;

// --- Rendering ---------------------------------------------------------------------------------------------------
let host: HTMLElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

async function show(node: ReactNode) {
  await act(async () => root.render(node));
  await settle();
}

async function settle() {
  for (let i = 0; i < 6; i++) await act(async () => await Promise.resolve());
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
/** The accessible name: aria-label, else the text without what is hidden from screen readers. */
function nameOf(el: Element): string {
  const label = el.getAttribute("aria-label");
  if (label) return label;
  const copy = el.cloneNode(true) as Element;
  copy.querySelectorAll('[aria-hidden="true"]').forEach((n) => n.remove());
  return text(copy);
}
const pressable = (within: ParentNode = document) =>
  Array.from(within.querySelectorAll<HTMLElement>("button, a[href], [role='button']"));
const named = (name: string, within: ParentNode = document) =>
  pressable(within).filter((el) => nameOf(el) === name);
/** Text a person sees: not inside anything hidden from them. */
function visibleText(within: Element): string {
  const copy = within.cloneNode(true) as Element;
  copy.querySelectorAll('[aria-hidden="true"], [hidden], .vh').forEach((n) => n.remove());
  return text(copy);
}

function json(status: number, data: unknown) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

// =================================================================================================================
// V-ACC.teamup/4
// =================================================================================================================
describe("V-ACC.teamup/4: Waiting for Ravi with Withdraw, the same on every screen that shows that idea", () => {
  // V-ACC.teamup/4: S-H2 card covered in crew-screen.test.ts once f/crew-search lands (Find your crew and Home's
  // crew cards are on f/crew-search-4, not on main yet).

  /** The same words on every screen: the waiting line and the Withdraw control's name, exactly. */
  const SAME = ["Waiting for Ravi", "Withdraw"];

  it("V-ACC.teamup/4 S-09: the idea page's Team up card", async () => {
    await show(createElement(TeamUpCard, { ideaId: IDEA, t: S09 }));
    const card = host.querySelector(".ip-team")!;
    expect(visibleText(card)).toContain("Waiting for Ravi");
    const withdraw = named("Withdraw", card);
    expect(withdraw).toHaveLength(1);
    expect(named("Team up", card)).toHaveLength(0);
    expect([text(card.querySelector(".ip-team-wait p")), nameOf(withdraw[0]!)]).toEqual(SAME);
  });

  it("V-ACC.teamup/4 S-05: the similar idea's tile on Check it", async () => {
    await show(
      createElement(
        "div",
        { className: "ck" },
        createElement(SimilarGrid, {
          draftId: "0b6f7a52-3c1e-4d7a-9f00-1a2b3c4d5e6f",
          draftTitle: "Investors call to ask why a redemption was rejected",
          draftSummary: "The rejection SMS only gives a code, such as R07.",
          load: { state: "ok", matches: [MATCH] },
          merge: null,
          keptSeparate: false,
          onShowAgain: () => undefined,
          onSent: () => undefined,
          onWithdrawn: () => undefined,
          onWithdraw: async () => undefined,
        }),
      ),
    );
    const tile = host.querySelectorAll(".simgrid > li")[1]!;
    expect(visibleText(tile)).toContain("Waiting for Ravi");
    const withdraw = named("Withdraw", tile);
    expect(withdraw).toHaveLength(1);
    expect(named(`Team up on ${TITLE}`, tile)).toHaveLength(0);
    expect([text(tile.querySelector(".tuwait")), nameOf(withdraw[0]!)]).toEqual(SAME);
  });

  async function openPreview() {
    await show(
      createElement(SimilarGrid, {
        draftId: "0b6f7a52-3c1e-4d7a-9f00-1a2b3c4d5e6f",
        draftTitle: "Investors call to ask why a redemption was rejected",
        draftSummary: "",
        load: { state: "ok", matches: [MATCH] },
        merge: null,
        keptSeparate: false,
        onShowAgain: () => undefined,
        onSent: () => undefined,
        onWithdrawn: () => undefined,
        onWithdraw: async () => undefined,
      }),
    );
    const open = named(`Preview ${TITLE}`)[0]!;
    await act(async () => open.click());
    await settle();
    return document.querySelector<HTMLElement>('[role="dialog"]')!;
  }

  it("V-ACC.teamup/4 C-PREVIEW: the preview of that idea says Waiting for Ravi where Team up was", async () => {
    const dialog = await openPreview();
    expect(visibleText(dialog)).toContain("Waiting for Ravi");
    expect(named("Team up", dialog)).toHaveLength(0);
  });

  // Lane C: C-PREVIEW/7 replaces the button with a green status only ("Waiting for Ravi"), so the preview has no
  // Withdraw; V-ACC.teamup/4 asks for Withdraw on every screen that shows the idea. The pack disagrees with itself:
  // the product lead rules, then lane C either adds Withdraw or the row names the preview as status-only.
  it.fails(
    "V-ACC.teamup/4 C-PREVIEW: lane C — the preview also offers Withdraw (C-PREVIEW/7 draws a status only)",
    async () => {
      const dialog = await openPreview();
      expect(named("Withdraw", dialog)).toHaveLength(1);
    },
  );

  it("V-ACC.teamup/4 C-SHEET-TEAMUP.after: once sent, the sheet tells its opener Waiting for Ravi with Withdraw", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit = {}) => {
        const key = `${init.method ?? "GET"} ${url}`;
        if (key === `GET /api/ideas/${IDEA}/team-up`)
          return json(200, {
            idea_id: IDEA,
            lead: RAVI,
            me: null,
            crew_count: 4,
            can_request: true,
            why_not: null,
            request: null,
            after: null,
          });
        if (key === `GET /api/ideas/${IDEA}/team-up/draft-note`)
          return json(200, {
            note: NOTE,
            own_ideas: [],
            idea: { id: IDEA, title: TITLE },
            lead: RAVI,
            min_chars: 30,
          });
        if (key === "GET /api/me") return json(200, { name: KAVYA.name, contributor_code: "SYN-00017" });
        if (key === `POST /api/ideas/${IDEA}/team-up`)
          return json(201, { ...REQUEST, request: "teamup", after: AFTER });
        return json(404, { error: { code: "not_found", message: "We couldn’t find that." } });
      }),
    );
    let after: Sent["after"] = null;
    /** A host that draws its opener from what the sheet hands back, as C-SHEET-TEAMUP.after says. */
    function Host() {
      const [open, setOpen] = useState(true);
      const [done, setDone] = useState<Sent["after"]>(null);
      return createElement(
        Fragment,
        null,
        done
          ? createElement(
              "p",
              { className: "opener" },
              createElement("span", null, done.line),
              " ",
              createElement("button", { type: "button" }, done.action?.label),
            )
          : null,
        createElement(TeamUpSheet, {
          ideaId: IDEA,
          open,
          onClose: () => setOpen(false),
          onSent: (s: Sent) => {
            after = s.after;
            setDone(s.after);
          },
        }),
      );
    }
    await show(createElement(Host));
    await act(async () => named("Send to Ravi")[0]!.click());
    await settle();
    expect(after).toMatchObject({ line: "Waiting for Ravi", action: { label: "Withdraw" } });
    const opener = document.querySelector(".opener")!;
    expect(visibleText(opener)).toContain("Waiting for Ravi");
    expect([text(opener.querySelector("span")), nameOf(named("Withdraw", opener)[0]!)]).toEqual(SAME);
  });
});

// =================================================================================================================
// V-ACC.teamup/6
// =================================================================================================================
describe("V-ACC.teamup/6: each of Ravi's answers on S-H2B shows its result in place, with no Undo", () => {
  const LEAD_VIEW = {
    id: RID,
    request: "merge",
    idea_id: IDEA,
    from: KAVYA,
    note: NOTE,
    brought: [
      {
        id: "IDEA-2026-001481",
        title: "Investors call to ask why a redemption was rejected",
        status: "with_review_desk",
        summary: "About 40 investors a day call the branch.",
        byline: "Kavya Menon, Investor service, Hyderabad. Shared Saturday.",
      },
    ],
    state: "sent",
    sent_at: "2026-11-18T10:30:00+05:30",
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
  };
  const ITEM = {
    id: "41",
    kind: "teamup_request",
    from: KAVYA,
    idea: { id: IDEA, title: TITLE, status: "with_review_desk" },
    line: "asks to team up and merge their idea into yours",
    at: "2026-11-18T10:30:00+05:30",
    unread: false,
    needs_you: true,
    archived: false,
    body: { heading: "Merge request", note: "", sender: "Kavya Menon", request_id: RID },
    actions: [
      { label: "Decline", style: "text", op: "decline" },
      { label: "Team up only", style: "line", op: "team_only" },
      { label: "Merge it", style: "primary", op: "merge" },
    ],
  } as InboxEntry;
  const HELLO = { label: "Say hello to Kavya", to: `/ideas/${IDEA}/conversation` };
  /** The worker's answers (`teamup/rules.py lead_result`, `say_hello`), S-H2B.states. */
  const RESULTS = {
    merge: {
      result: {
        state: "merged",
        text: "Merged. Kavya’s idea is now part of yours, and they are on your crew, credited. We’ve told them.",
      },
      say_hello: HELLO,
    },
    team_only: {
      result: {
        state: "teamed_up",
        text: "Teamed up. Kavya is on your crew. Their idea stays separate, and they send it on its own. We’ve told them.",
      },
      say_hello: HELLO,
    },
    decline: {
      result: {
        state: "declined",
        text: "Declined. Kavya sees your reason: “The crew is full for now” They can send theirs on its own.",
      },
      say_hello: null,
    },
  } as const;

  let answered: unknown[] = [];
  beforeEach(() => {
    answered = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit = {}) => {
        if (url === `/api/team-up/${RID}`) return json(200, LEAD_VIEW);
        if (url === `/api/team-up/${RID}/answer`) {
          const body = JSON.parse(String(init.body)) as { answer: keyof typeof RESULTS };
          answered.push(body);
          return json(200, RESULTS[body.answer]);
        }
        return json(404, { error: { code: "not_found", message: "We couldn’t find that." } });
      }),
    );
  });

  function Reader() {
    const view = useRequest(
      ITEM,
      () => undefined,
      () => undefined,
    );
    return view ? createElement(Fragment, null, view.body, view.bar) : null;
  }

  async function press(name: string) {
    const [b] = named(name, host);
    expect(b, name).toBeDefined();
    await act(async () => b!.click());
    await settle();
  }

  const answersLeft = () =>
    ["Decline", "Team up only", "Merge it", "Approve"].filter((n) => named(n, host).length > 0);
  const undo = () => [...pressable(host).map(nameOf), visibleText(host)].filter((s) => /\bundo\b/i.test(s));

  it("V-ACC.teamup/6: the three answers are offered in the order Decline, Team up only, Merge it", async () => {
    await show(createElement(Reader));
    expect(
      pressable(host)
        .map(nameOf)
        .filter((n) => answersLeft().includes(n)),
    ).toEqual(["Decline", "Team up only", "Merge it"]);
    expect(undo()).toEqual([]);
  });

  it("V-ACC.teamup/6 Merge it: the merged line and Say hello to Kavya; no Undo, and no answer left to press", async () => {
    await show(createElement(Reader));
    await press("Merge it");
    expect(answered).toEqual([{ answer: "merge" }]);
    expect(text(host.querySelector(".ibx-result"))).toBe(RESULTS.merge.result.text);
    expect(named("Say hello to Kavya", host)).toHaveLength(1);
    expect(answersLeft()).toEqual([]);
    expect(undo()).toEqual([]);
  });

  it("V-ACC.teamup/6 Team up only: the teamed-up line and Say hello to Kavya; no Undo, and no answer left to press", async () => {
    await show(createElement(Reader));
    await press("Team up only");
    expect(answered).toEqual([{ answer: "team_only" }]);
    expect(text(host.querySelector(".ibx-result"))).toBe(RESULTS.team_only.result.text);
    expect(named("Say hello to Kavya", host)).toHaveLength(1);
    expect(answersLeft()).toEqual([]);
    expect(undo()).toEqual([]);
  });

  it("V-ACC.teamup/6 Decline: with a reason, the declined line and Next; no Undo, and no answer left to press", async () => {
    await show(createElement(Reader));
    await press("Decline");
    const field = host.querySelector<HTMLTextAreaElement>("#ibx-reason")!;
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
    await act(async () => {
      setter.call(field, "The crew is full for now");
      field.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await press("Decline the request");
    expect(answered).toEqual([{ answer: "decline", reason: "The crew is full for now" }]);
    expect(text(host.querySelector(".ibx-result"))).toBe(RESULTS.decline.result.text);
    expect(named("Next", host)).toHaveLength(1);
    expect(answersLeft()).toEqual([]);
    expect(undo()).toEqual([]);
  });
});

// =================================================================================================================
// CSS as written (the rules a browser would apply), for the motion rows
// =================================================================================================================
const APP = resolve(__dirname, "../../src/app");
type Rule = { at: string; selectors: string[]; decls: Map<string, string> };

/** Every style rule in a sheet: its enclosing at-rules (joined), its selectors and its declarations. */
function rules(sheet: string): Rule[] {
  const clean = readFileSync(resolve(APP, sheet), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  const out: Rule[] = [];
  const stack: string[] = [];
  let buf = "";
  let current: Rule | null = null;
  const take = () => {
    const m = buf.trim().match(/^([\w-]+)\s*:\s*([\s\S]+)$/);
    if (m && current) current.decls.set(m[1]!, m[2]!.trim());
    buf = "";
  };
  for (const ch of clean) {
    if (ch === "{") {
      const head = buf.trim().replace(/\s+/g, " ");
      buf = "";
      if (head.startsWith("@")) stack.push(head);
      else {
        current = { at: stack.join(" "), selectors: head.split(",").map((s) => s.trim()), decls: new Map() };
        stack.push("");
        out.push(current);
      }
    } else if (ch === "}") {
      if (stack.pop() === "" && current) {
        take();
        current = null;
      }
      buf = "";
    } else if (ch === ";" && current) take();
    else buf += ch;
  }
  return out;
}

// =================================================================================================================
// V-ACC.teamup/7
// =================================================================================================================
describe("V-ACC.teamup/7: Find your crew, desktop: Next lifts the front card out to the right and tucks it behind the pile", () => {
  /** The Deck as S-H2 holds it: the page keeps the index. */
  function Crew() {
    const [at, setAt] = useState(0);
    const cards = [
      "Rejection SMS codes confuse investors",
      "No script for calls about rejections",
      "Branch staff cannot read the SMS codes",
    ].map((t) =>
      createElement(
        "article",
        { className: "kit-dcard" },
        createElement("h3", null, t),
        createElement("button", { type: "button" }, "Team up"),
      ),
    );
    return createElement(Deck, { label: "Ideas close to yours", cards, index: at, onIndexChange: setAt });
  }

  const css = rules("components.css");
  const decl = (selector: string, prop: string, at = "") =>
    css
      .filter((r) => r.at === at && r.selectors.includes(selector))
      .reduce<string | undefined>((v, r) => r.decls.get(prop) ?? v, undefined);
  const frames = (name: string) =>
    new Map(
      css
        .filter((r) => r.at === `@keyframes ${name}`)
        .flatMap((r) => r.selectors.map((s) => [s, r.decls] as const)),
    );
  /** translate(46%, -18px) rotate(6deg) / translateY(26px) scale(0.9) / none, read into numbers. */
  function motion(transform: string | undefined) {
    const t = transform ?? "none";
    const tr = t.match(/translate\(\s*([-\d.]+)(%|px)?\s*,\s*([-\d.]+)px\s*\)/);
    const tx = t.match(/translateX\(\s*([-\d.]+)/);
    const ty = t.match(/translateY\(\s*([-\d.]+)px/);
    return {
      x: tr ? Number(tr[1]) : tx ? Number(tx[1]) : 0,
      y: tr ? Number(tr[3]) : ty ? Number(ty[1]) : 0,
      rotate: Number(t.match(/rotate\(\s*([-\d.]+)deg/)?.[1] ?? 0),
      scale: Number(t.match(/scale\(\s*([-\d.]+)/)?.[1] ?? 1),
    };
  }

  it("V-ACC.teamup/7: pressing Next marks the front card as the one going to the back and brings the next to the front", async () => {
    await show(createElement(Crew));
    const cards = () => Array.from(host.querySelectorAll<HTMLElement>(".deck-track > .dcard"));
    expect(cards().map((c) => c.className)).toEqual(["dcard cur", "dcard nx", "dcard"]);
    await act(async () => named("Next idea", host)[0]!.click());
    expect(cards().map((c) => c.className)).toEqual(["dcard toback", "dcard cur", "dcard nx"]);
    expect(visibleText(cards()[1]!)).toContain("No script for calls about rejections");
    expect(text(host.querySelector('[aria-live="polite"]'))).toBe("Idea 2 of 3");
  });

  it("V-ACC.teamup/7 C-CREW-DECK.behaviour/2: the full-motion path lifts right with a tilt, then tucks behind the pile; it never slides sideways", () => {
    // The outgoing card's animation, outside any reduced-motion query: 620 ms on the pack's curve
    const anim = decl(".dcard.toback", "animation")!;
    expect(anim).toMatch(/^deckToBack 0\.62s cubic-bezier\(0\.45, 0, 0\.25, 1\) both$/);
    const front = Number(decl(".dcard.cur", "z-index"));
    const next = Number(decl(".dcard.nx", "z-index"));
    expect(front).toBeGreaterThan(next);

    const kf = frames("deckToBack");
    const keys = [...kf.keys()].sort((a, b) => parseFloat(a) - parseFloat(b));
    expect(keys[0]).toBe("0%");
    expect(keys[keys.length - 1]).toBe("100%");
    // Lift: out to the right (46% of its width), up 18px, tilted 6°, still in front of the pile
    const lift = keys.map((k) => ({ k, d: kf.get(k)! })).find((f) => motion(f.d.get("transform")).x > 0);
    expect(lift, "a frame where the card is out to the right").toBeDefined();
    const out = motion(lift!.d.get("transform"));
    expect(out).toMatchObject({ x: 46, y: -18, rotate: 6, scale: 1 });
    expect(Number(lift!.d.get("z-index"))).toBeGreaterThanOrEqual(front);
    // Tuck: it ends behind the next card, smaller, lower, faded, and back over the pile, not off to the side
    const end = kf.get("100%")!;
    const tucked = motion(end.get("transform"));
    expect(tucked.x).toBe(0);
    expect(tucked.y).toBe(26);
    expect(tucked.scale).toBeCloseTo(0.9);
    expect(Number(end.get("z-index"))).toBeLessThan(next);
    expect(Number(end.get("opacity"))).toBe(0);
    // It drops behind the pile before it comes back over it: the z-index falls right after the lift
    const lifted = parseFloat(lift!.k);
    const behind = keys.find((k) => parseFloat(k) > lifted && Number(kf.get(k)!.get("z-index")) < next);
    expect(behind, "a frame just after the lift where the card goes behind").toBeDefined();
    expect(parseFloat(behind!) - lifted).toBeLessThanOrEqual(5);
    // Not a slide: no frame moves it sideways without lifting, tilting or tucking it
    for (const k of keys) {
      const m = motion(kf.get(k)!.get("transform"));
      if (m.x !== 0) expect(m.y !== 0 || m.rotate !== 0 || m.scale !== 1, k).toBe(true);
    }
  });

  it("V-ACC.teamup/7 C-CREW-DECK.behaviour/5: only with reduced motion do the cards swap without the flight", () => {
    const reduced = css.filter(
      (r) => /prefers-reduced-motion:\s*reduce/.test(r.at) && r.selectors.includes(".dcard.toback"),
    );
    expect(reduced.some((r) => r.decls.get("animation") === "none")).toBe(true);
    expect(decl(".dcard.toback", "animation")).not.toBe("none");
  });
});

// =================================================================================================================
// V-ACC.teamup/9
// =================================================================================================================
describe("V-ACC.teamup/9: Home's Ones, the pointer over the cards: one card per wheel step, and the page scrolls on at the ends", () => {
  const POSTS = ["Rohit", "Sunita", "Arjun", "Meena"].map((n) =>
    createElement("article", { className: "opost" }, `${n}’s fix shipped`),
  );
  let clock = Date.parse("2026-11-18T05:00:00Z");

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(clock);
  });

  /** One wheel step over the cards, a moment after the last; whether the page was kept from scrolling. */
  async function wheel(deltaY: number): Promise<boolean> {
    clock += 450;
    vi.setSystemTime(clock);
    const view = host.querySelector(".fan-view")!;
    const e = new WheelEvent("wheel", { deltaY, bubbles: true, cancelable: true });
    await act(async () => {
      view.dispatchEvent(e);
    });
    return e.defaultPrevented;
  }
  const position = () => text(host.querySelector(".fan-pos"));

  async function fan() {
    await show(
      createElement(OnesFan, {
        cards: POSTS,
        empty: createElement("p", null, "No Ones yet."),
        companion: createElement("p", null, "The next One could be you."),
      }),
    );
  }

  it("V-ACC.teamup/9 C-ONES-FAN.behaviour/4: wheel down, then up: one card forward, then one back, per step", async () => {
    await fan();
    expect(position()).toBe("Post 1 of 4");
    expect(await wheel(100)).toBe(true); // stacked: the first step spreads the fan
    expect(host.querySelector(".fan-view")!.className).toBe("fan-view spread");
    expect(position()).toBe("Post 1 of 4");
    const steps: string[] = [];
    for (const dy of [100, 100, -100, -100]) {
      expect(await wheel(dy)).toBe(true);
      steps.push(position());
    }
    expect(steps).toEqual(["Post 2 of 4", "Post 3 of 4", "Post 2 of 4", "Post 1 of 4"]);
  });

  it("V-ACC.teamup/9 C-ONES-FAN.behaviour/4: at the last card wheel down scrolls the page on; at the first, wheel up does", async () => {
    await fan();
    await wheel(100);
    for (const n of [2, 3, 4]) {
      expect(await wheel(100)).toBe(true);
      expect(position()).toBe(`Post ${n} of 4`);
    }
    expect(await wheel(100)).toBe(false); // the page scrolls on; nothing holds it
    expect(position()).toBe("Post 4 of 4");
    expect(await wheel(100)).toBe(false);
    for (const n of [3, 2, 1]) {
      expect(await wheel(-100)).toBe(true);
      expect(position()).toBe(`Post ${n} of 4`);
    }
    expect(await wheel(-100)).toBe(false);
    expect(position()).toBe("Post 1 of 4");
  });
});
