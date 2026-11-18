// @vitest-environment jsdom
/**
 * C-SHEET-TEAMUP, the team-up request sheet (BLD-F070 to BLD-F073): each step (compose, the Check it choice, sending,
 * sent) and each error, against a mocked fetch; the dialog's name, description and focus; the host helper. Copy from
 * C-SHEET-TEAMUP and reference/copy/Crew.md (view=Request, view=Request sent). Synthetic people only: the pack's
 * fictional cast (Kavya asks, Ravi leads).
 */
import { act, createElement, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/motion/spark", () => ({ sparkBurst: vi.fn() }));

const { sparkBurst } = await import("@/lib/motion/spark");
const { TEAMUP_COPY, TeamUpSheet, errorFrom, leadWord, noteHint, quotedList, teamUpOpener, useTeamUpSheet } =
  await import("@/components/teamup/teamup-sheet");
type Props = import("@/components/teamup/teamup-sheet").TeamUpSheetProps;

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- Fixtures (synthetic) --------------------------------------------------------------------------------------
const RAVI = { id: "p-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" };
const KAVYA = { id: "p-kavya", name: "Kavya Iyer", first_name: "Kavya", initials: "KI" };
const TITLE = "Rejection SMS codes confuse investors";
const DRAFTED =
  "I’m in Investor service (Senior executive). I shared “Investors call to ask why a redemption was rejected”, which is close to yours, and I can bring what I learned from it.";
const NOTE =
  "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07. I can bring the call log and real examples of what investors ask.";
const OWN = [
  {
    id: "IDEA-2026-001481",
    title: "Investors call to ask why a redemption was rejected",
    status: "with_review_desk",
    meta: "IDEA-2026-001481, with the review desk",
  },
  {
    id: "IDEA-2026-001502",
    title: "No script for calls about rejections",
    status: "shared",
    meta: "IDEA-2026-001502, shared",
  },
];
const DRAFT = "7f1c2a9e-0b3d-4e5f-8a6b-1c2d3e4f5a6b";
const ME_KAVYA = { name: KAVYA.name, email: "kavya.iyer@example.test", contributor_code: "SYN-00017" };
const ME_ARJUN = { name: "Arjun Rao", email: "arjun.rao@example.test", contributor_code: "SYN-00031" };
const WAITING = {
  state: "waiting",
  line: "Waiting for Ravi",
  detail: "Ravi reads your note, then approves or declines. You’ll hear in your Inbox.",
  action: { label: "Withdraw", op: "withdraw" },
};

let seq = 1400;
let IDEA = "";
const U = {
  mine: () => `GET /api/ideas/${IDEA}/team-up`,
  note: () => `GET /api/ideas/${IDEA}/team-up/draft-note`,
  send: () => `POST /api/ideas/${IDEA}/team-up`,
  merge: () => `POST /api/drafts/${DRAFT}/merge-request`,
  withdraw: (id: string) => `DELETE /api/team-up/${id}`,
  me: "GET /api/me",
};

const free = () => ({
  idea_id: IDEA,
  lead: RAVI,
  me: null,
  crew_count: 4,
  can_request: true,
  why_not: null,
  request: null,
  after: null,
});
const drafted = () => ({
  note: DRAFTED,
  own_ideas: OWN,
  idea: { id: IDEA, title: TITLE },
  lead: RAVI,
  min_chars: 30,
  max_chars: 600,
});
const request = (note: string, brought: typeof OWN = [], state = "sent") => ({
  id: "req-1",
  request: "teamup",
  idea_id: IDEA,
  from: KAVYA,
  note,
  brought: brought.map(({ id, title, status }) => ({ id, title, status })),
  state,
  sent_at: "2026-11-17T10:30:00+05:30",
  after: WAITING,
});

// --- A fetch that answers by method and path -------------------------------------------------------------------
type Answer = { status?: number; body?: unknown; raw?: string; offline?: boolean; wait?: Promise<void> };
let routes: Record<string, Answer | ((body: unknown) => Answer)> = {};
type Call = { key: string; headers: Record<string, string>; body: unknown };
let calls: Call[] = [];

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const key = `${init.method ?? "GET"} ${url}`;
      const body = typeof init.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
      calls.push({ key, headers: (init.headers ?? {}) as Record<string, string>, body });
      const route = routes[key];
      const a: Answer =
        typeof route === "function" ? route(body) : (route ?? { status: 404, body: { error: "not_found" } });
      if (a.wait) await a.wait;
      if (a.offline) throw new TypeError("Failed to fetch");
      const status = a.status ?? 200;
      return {
        ok: status >= 200 && status < 300,
        status,
        json: () =>
          a.raw !== undefined ? Promise.reject(new SyntaxError("bad json")) : Promise.resolve(a.body),
      };
    }),
  );
}

const posts = () => calls.filter((c) => !c.key.startsWith("GET "));

// --- Rendering and the DOM -------------------------------------------------------------------------------------
let host: HTMLElement;
let root: Root;

beforeEach(() => {
  IDEA = `IDEA-2026-00${seq++}`;
  calls = [];
  routes = {
    [U.mine()]: { body: free() },
    [U.note()]: { body: drafted() },
    [U.me]: { body: ME_KAVYA },
  };
  mockFetch();
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

async function settle() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
}

async function render(props: Partial<Props> = {}) {
  const onClose = vi.fn();
  const onSent = vi.fn();
  const onWithdrawn = vi.fn();
  await act(async () =>
    root.render(
      createElement(TeamUpSheet, { ideaId: IDEA, open: true, onClose, onSent, onWithdrawn, ...props }),
    ),
  );
  await settle();
  return { onClose, onSent, onWithdrawn };
}

/** A page with a "Team up" button that opens the sheet, as a host wires it. */
function Harness(props: Partial<Props> & { log: string[] }) {
  const { log, ...rest } = props;
  const [open, setOpen] = useState(false);
  return createElement(
    "main",
    null,
    createElement("button", { type: "button", id: "opener", onClick: () => setOpen(true) }, "Team up"),
    createElement(TeamUpSheet, {
      ideaId: IDEA,
      ...rest,
      open,
      onClose: () => {
        log.push("close");
        setOpen(false);
      },
    }),
  );
}

async function openFromHarness(props: Partial<Props> = {}, log: string[] = []) {
  await act(async () => root.render(createElement(Harness, { ...props, log })));
  const opener = document.getElementById("opener") as HTMLButtonElement;
  opener.focus();
  await act(async () => opener.click());
  await settle();
  return { log, opener };
}

const dialog = () => document.querySelector<HTMLElement>('[role="dialog"]');
const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const byIds = (ids: string | null) =>
  (ids ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((id) => text(document.getElementById(id)))
    .join(" ");
/** Text a screen reader reads: aria-hidden parts left out (a busy button's spare label, icons). */
function spoken(el: Node): string {
  if (el.nodeType === Node.TEXT_NODE) return el.textContent ?? "";
  if (el instanceof Element && el.getAttribute("aria-hidden") === "true") return "";
  return Array.from(el.childNodes).map(spoken).join("");
}
/** The accessible name, as far as this sheet needs it: aria-labelledby, aria-label, a <label for>, or the text. */
function nameOf(el: Element): string {
  if (el.hasAttribute("aria-labelledby")) return byIds(el.getAttribute("aria-labelledby"));
  if (el.hasAttribute("aria-label")) return el.getAttribute("aria-label")!;
  if (el.id) {
    const label = document.querySelector(`label[for="${el.id}"]`);
    if (label) return spoken(label).replace(/\s+/g, " ").trim();
  }
  return spoken(el).replace(/\s+/g, " ").trim();
}
const buttons = () => Array.from(document.querySelectorAll<HTMLButtonElement>("button"));
const button = (name: string) => buttons().find((b) => nameOf(b) === name);
const sendButton = () => button("Send to Ravi")!;
const note = () => dialog()!.querySelector<HTMLTextAreaElement>("textarea")!;
const radio = (name: string) =>
  Array.from(document.querySelectorAll<HTMLInputElement>('input[type="radio"]')).find((r) =>
    nameOf(r).startsWith(name),
  );
const checkbox = (title: string) =>
  Array.from(document.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')).find((c) =>
    text(c.closest("label")).startsWith(title),
  )!;
const alerts = () => Array.from(dialog()!.querySelectorAll('[role="alert"]')).map(text);

async function type(value: string) {
  const el = note();
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
  await act(async () => {
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function click(el: HTMLElement | undefined) {
  expect(el).toBeDefined();
  await act(async () => el!.click());
  await settle();
}

async function press(key: string, init: KeyboardEventInit = {}) {
  const target = (document.activeElement as HTMLElement | null) ?? document.body;
  await act(async () => {
    target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...init }));
  });
}

// --- Tests -----------------------------------------------------------------------------------------------------
describe("C-SHEET-TEAMUP.compose (BLD-F070)", () => {
  it("C-SHEET-TEAMUP.compose/1–6: loads my state and the drafted note; Team up with Ravi, the line, the note, None picked, Send to Ravi", async () => {
    await render();
    expect(calls.map((c) => c.key)).toEqual(expect.arrayContaining([U.mine(), U.note()]));
    expect(posts()).toHaveLength(0);

    const d = dialog()!;
    expect(d.getAttribute("aria-modal")).toBe("true");
    expect(nameOf(d)).toBe("Team up with Ravi");
    expect(document.getElementById(d.getAttribute("aria-labelledby")!)!.tagName).toBe("H2");
    expect(byIds(d.getAttribute("aria-describedby"))).toBe(
      `Ravi leads “${TITLE}” and decides who joins. Tell Ravi what you bring.`,
    );
    // The note: labelled, pre-filled from the person's own idea, with the drafted hint.
    expect(nameOf(note())).toBe("Your note to Ravi");
    expect(note().value).toBe(DRAFTED);
    expect(note().rows).toBe(4);
    expect(text(d)).toContain("We drafted this from your idea. Change anything you like.");
    expect(byIds(note().getAttribute("aria-describedby"))).toBe(TEAMUP_COPY.hintDrafted);
    // Bring your ideas along, Optional, collapsed, nothing picked (C-DROPDOWN/2).
    const field = button("Bring your ideas along: None picked")!;
    expect(field).toBeDefined();
    expect(field.getAttribute("aria-expanded")).toBe("false");
    expect(text(d)).toContain("Bring your ideas along Optional");
    expect(text(d)).toContain("Ravi sees your name, your note.");
    // One button, Send to Ravi, available.
    expect(sendButton().getAttribute("aria-disabled")).toBeNull();
    expect(button("Close without sending")).toBeDefined();
    // The avatar pair: mine (from /api/me) and the lead's, decorative.
    const pair = d.querySelector(".tus-pair")!;
    expect(pair.getAttribute("aria-hidden")).toBe("true");
    expect(Array.from(pair.querySelectorAll(".av")).map(text)).toEqual(["KI", "RN"]);
  });

  it("C-SHEET-TEAMUP.a11y: focus starts in the note with the cursor at the end", async () => {
    await render();
    expect(document.activeElement).toBe(note());
    expect(note().selectionStart).toBe(DRAFTED.length);
    expect(note().selectionEnd).toBe(DRAFTED.length);
  });

  it("C-SHEET-TEAMUP.compose/3, /6: under 30 characters warns and Send focuses the note; edited and long enough, Looks good.", async () => {
    await render();
    await type("I can help.");
    expect(alerts()).toEqual(["Add a little more: at least 30 characters."]);
    expect(note().getAttribute("aria-describedby")).toBeTruthy();
    expect(sendButton().getAttribute("aria-disabled")).toBe("true");
    (document.activeElement as HTMLElement).blur();
    await click(sendButton());
    expect(posts()).toHaveLength(0);
    expect(document.activeElement).toBe(note());

    await type(NOTE);
    expect(alerts()).toEqual([]);
    expect(text(dialog())).toContain("Looks good.");
    expect(text(dialog())).not.toContain(TEAMUP_COPY.hintDrafted);
    expect(sendButton().getAttribute("aria-disabled")).toBeNull();
  });

  it("C-SHEET-TEAMUP.compose/3: a note over 600 characters cannot be sent (V-FIELDS.teamup/1)", async () => {
    await render();
    await type("x".repeat(601));
    expect(alerts()).toEqual(["Keep your note to 600 characters."]);
    expect(sendButton().getAttribute("aria-disabled")).toBe("true");
  });

  it("C-SHEET-TEAMUP.compose/4–5: one idea brought reads its title, two read 2 ideas picked; the privacy line follows; the send carries them", async () => {
    routes[U.send()] = (b) => ({ status: 201, body: request((b as { note: string }).note, OWN) });
    await render();
    await click(button("Bring your ideas along: None picked"));
    expect(text(dialog())).toContain("IDEA-2026-001481, with the review desk");

    await click(checkbox(OWN[0]!.title));
    expect(button(`Bring your ideas along: ${OWN[0]!.title}`)).toBeDefined();
    expect(text(dialog())).toContain("Ravi sees your name, your note and the idea you bring.");

    await click(checkbox(OWN[1]!.title));
    expect(button("Bring your ideas along: 2 ideas picked")).toBeDefined();
    expect(text(dialog())).toContain("Ravi sees your name, your note and the ideas you bring.");

    await click(sendButton());
    expect(posts()).toHaveLength(1);
    expect(posts()[0]!.key).toBe(U.send());
    expect(posts()[0]!.body).toEqual({ note: DRAFTED, brought_idea_ids: [OWN[0]!.id, OWN[1]!.id] });
  });

  it("C-SHEET-TEAMUP: with no shared idea of their own, the list says so", async () => {
    routes[U.note()] = { body: { ...drafted(), own_ideas: [] } };
    await render();
    await click(button("Bring your ideas along: None picked"));
    expect(text(dialog())).toContain("You have no shared ideas to bring yet.");
  });
});

describe("C-SHEET-TEAMUP sending and sent (BLD-F070)", () => {
  it("C-SHEET-TEAMUP sending: Sending… while it goes, one POST with an Idempotency-Key, the spark marks the send", async () => {
    let release!: () => void;
    const wait = new Promise<void>((r) => (release = r));
    routes[U.send()] = { status: 201, body: request(DRAFTED), wait };
    await render();
    const send = sendButton();
    await act(async () => send.click());
    expect(send.getAttribute("aria-busy")).toBe("true");
    expect(text(send)).toContain("Sending…");
    await act(async () => send.click()); // a second click while busy sends nothing
    expect(posts()).toHaveLength(1);
    expect(posts()[0]!.headers["Idempotency-Key"]).toMatch(/\S{8,}/);
    expect(posts()[0]!.headers["content-type"]).toBe("application/json");

    await act(async () => release());
    await settle();
    expect(sparkBurst).toHaveBeenCalledWith(send);
    expect(text(dialog())).toContain("Sent to Ravi");
  });

  it("C-SHEET-TEAMUP sending: a retry of the same request reuses its key; a changed note gets a new one (BLD-F026)", async () => {
    let n = 0;
    routes[U.send()] = () => (n++ < 2 ? { offline: true } : { status: 201, body: request(NOTE) });
    await render();
    await click(sendButton());
    await click(sendButton());
    const [a, b] = posts();
    expect(a!.headers["Idempotency-Key"]).toBe(b!.headers["Idempotency-Key"]);
    await type(NOTE);
    await click(sendButton());
    expect(posts()[2]!.headers["Idempotency-Key"]).not.toBe(a!.headers["Idempotency-Key"]);
  });

  it("C-SHEET-TEAMUP.sent: the sheet changes in place: Sent to Ravi, the line, the note back, Bringing …, Withdraw request, Done", async () => {
    routes[U.send()] = (b) => ({ status: 201, body: request((b as { note: string }).note, [OWN[0]!]) });
    const { onSent, onClose } = await render();
    await click(button("Bring your ideas along: None picked"));
    await click(checkbox(OWN[0]!.title));
    await type(NOTE);
    await click(sendButton());

    const d = dialog()!;
    // The same dialog, still named for the lead, so the opener's locator keeps it (J-TEAMUP/3, J-SIMILAR/3).
    expect(nameOf(d)).toBe("Team up with Ravi");
    const status = d.querySelector('[role="status"]')!;
    expect(text(status)).toContain("Sent to Ravi");
    expect(text(status)).toContain(
      "Ravi reads your note, then approves or declines. You’ll hear in your Inbox.",
    );
    expect(byIds(d.getAttribute("aria-describedby"))).toBe(TEAMUP_COPY.sentLine("Ravi"));
    expect(text(status)).toContain("Your note");
    expect(text(status)).toContain(NOTE);
    expect(text(status)).toContain(`Bringing “${OWN[0]!.title}”`);
    expect(d.querySelector("textarea")).toBeNull();
    expect(button("Withdraw request")).toBeDefined();
    expect(document.activeElement).toBe(button("Done"));

    expect(onSent).toHaveBeenCalledTimes(1);
    expect(onSent.mock.calls[0]![0]).toMatchObject({
      kind: "teamup",
      id: "req-1",
      ideaId: IDEA,
      note: NOTE,
      brought: [OWN[0]!.title],
      after: WAITING,
    });
    await click(button("Done"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("C-SHEET-TEAMUP.sent: Keep looking on Find your crew in place of Done", async () => {
    routes[U.send()] = { status: 201, body: request(DRAFTED) };
    const { onClose } = await render({ doneLabel: "Keep looking" });
    await click(sendButton());
    expect(button("Done")).toBeUndefined();
    await click(button("Keep looking"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("C-SHEET-TEAMUP.sent: Withdraw request withdraws it and closes; the opener goes back to Team up", async () => {
    routes[U.send()] = { status: 201, body: request(DRAFTED) };
    routes[U.withdraw("req-1")] = { body: { ...request(DRAFTED, [], "withdrawn"), after: null } };
    const { onClose, onWithdrawn } = await render();
    await click(sendButton());
    await click(button("Withdraw request"));
    expect(posts().map((c) => c.key)).toEqual([U.send(), U.withdraw("req-1")]);
    expect(onWithdrawn).toHaveBeenCalledWith(expect.objectContaining({ id: "req-1", after: null }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("C-SHEET-TEAMUP.sent: a withdraw that fails says why and stays open", async () => {
    routes[U.send()] = { status: 201, body: request(DRAFTED) };
    routes[U.withdraw("req-1")] = {
      status: 409,
      body: { error: { code: "not_waiting", message: "This request has already been answered." } },
    };
    const { onClose, onWithdrawn } = await render();
    await click(sendButton());
    await click(button("Withdraw request"));
    expect(alerts()).toEqual(["This request has already been answered."]);
    expect(onWithdrawn).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("C-SHEET-TEAMUP, L-TEAMUP.rules/4: a request already waiting on Ravi opens on the sent step, with the note back", async () => {
    routes[U.mine()] = {
      body: {
        ...free(),
        can_request: false,
        why_not: "already_requested",
        request: request(NOTE),
        after: WAITING,
      },
    };
    await render();
    expect(nameOf(dialog()!)).toBe("Team up with Ravi");
    expect(text(dialog())).toContain("Sent to Ravi");
    expect(text(dialog())).toContain(NOTE);
    expect(button("Withdraw request")).toBeDefined();
    expect(note()).toBeNull();
  });
});

describe("C-SHEET-TEAMUP on Check it (L-MERGE.request, BLD-F071)", () => {
  it("C-SHEET-TEAMUP Check it: the choice replaces the dropdown; Keep mine separate is picked first; each says what it does", async () => {
    await render({ draftId: DRAFT });
    expect(button("Bring your ideas along: None picked")).toBeUndefined();
    const merge = radio("Ask Ravi to merge mine in")!;
    const separate = radio("Keep mine separate")!;
    expect(nameOf(merge)).toBe("Ask Ravi to merge mine in");
    expect(byIds(merge.getAttribute("aria-describedby"))).toBe(
      "Ravi decides. If Ravi accepts, yours joins that idea with credit to you. If not, you send yours on its own.",
    );
    expect(byIds(separate.getAttribute("aria-describedby"))).toBe("Team up, and send yours as its own idea");
    expect(separate.checked).toBe(true);
    expect(merge.name).toBe(separate.name);
    expect(text(merge.closest("fieldset")!.querySelector("legend"))).toBe("Your draft");
    expect(text(dialog())).toContain("We drafted this from your idea. Change anything you like.");
    expect(text(dialog())).toContain("Ravi sees your name, your note.");

    await click(merge);
    expect(merge.checked).toBe(true);
    expect(text(dialog())).toContain("Ravi sees your name, your note and the idea you bring.");
  });

  it("C-SHEET-TEAMUP Check it, BLD-F020: Keep mine separate sends a team-up with the draft's id", async () => {
    routes[U.send()] = (b) => ({ status: 201, body: request((b as { note: string }).note) });
    const { onSent } = await render({ draftId: DRAFT });
    await click(radio("Keep mine separate"));
    await type(NOTE);
    await click(sendButton());
    expect(posts()[0]!.key).toBe(U.send());
    expect(posts()[0]!.body).toEqual({ note: NOTE, brought_idea_ids: [], draft_id: DRAFT });
    expect(text(dialog())).toContain("Sent to Ravi");
    expect(text(dialog())).toContain(NOTE);
    expect(onSent.mock.calls[0]![0]).toMatchObject({ kind: "teamup", id: "req-1" });
  });

  it("C-SHEET-TEAMUP Check it, L-MERGE.request/1–4: Ask Ravi to merge mine in sends the draft's merge request", async () => {
    const after = {
      state: "waiting",
      label: "Waiting on Ravi to merge",
      line: "Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own.",
      action: { label: "Withdraw the request", op: "withdraw" },
      can_submit: false,
    };
    routes[U.merge()] = (b) => ({
      status: 201,
      body: {
        id: "mr-1",
        other_idea_id: IDEA,
        state: "waiting",
        note: (b as { note: string }).note,
        lead: RAVI,
        after,
      },
    });
    const { onSent } = await render({ draftId: DRAFT, draftTitle: "Failed SIP debit SMS gives no reason" });
    await click(radio("Ask Ravi to merge mine in"));
    await type(NOTE);
    await click(sendButton());
    expect(posts()[0]!.key).toBe(U.merge());
    expect(posts()[0]!.body).toEqual({ other_idea_id: IDEA, note: NOTE });
    expect(text(dialog())).toContain("Sent to Ravi");
    expect(text(dialog())).toContain("Bringing “Failed SIP debit SMS gives no reason”");
    expect(onSent.mock.calls[0]![0]).toMatchObject({ kind: "merge", id: "mr-1", after });

    // Withdraw on the sent step withdraws either kind through DELETE /api/team-up/:id (BLD-F010).
    routes[U.withdraw("mr-1")] = { body: { id: "mr-1", request: "merge", state: "withdrawn", after: null } };
    await click(button("Withdraw request"));
    expect(posts().at(-1)!.key).toBe(U.withdraw("mr-1"));
  });
});

describe("C-SHEET-TEAMUP errors: each with its ready-made message", () => {
  const worker = (status: number, code: string, message: string, field?: string) => ({
    status,
    body: { error: field ? { code, message, field } : { code, message } },
  });
  const cases: Array<[string, Answer, string]> = [
    ["already_requested", worker(409, "already_requested", "Waiting for Ravi"), "Waiting for Ravi"],
    ["already_on_crew", worker(409, "already_on_crew", "You’re on the crew."), "You’re on the crew."],
    [
      "idea_closed",
      worker(409, "idea_closed", "This idea is no longer open to team up."),
      "This idea is no longer open to team up.",
    ],
    ["not_found (BLD-F025)", worker(404, "not_found", "We couldn’t find that."), "We couldn’t find that."],
    [
      "key_reused (BLD-F026)",
      worker(
        409,
        "key_reused",
        "Something changed since you last sent this. Refresh the page and try again.",
      ),
      "Something changed since you last sent this. Refresh the page and try again.",
    ],
    [
      "paused (kill switch, BLD-F019)",
      {
        status: 503,
        body: { error: "paused", switch: "submissions", banner: "Sending is paused for a few minutes." },
      },
      "Sending is paused for a few minutes.",
    ],
    [
      "unavailable",
      {
        status: 503,
        body: {
          error: "unavailable",
          banner: "Something went wrong on our side. Please try again in a minute.",
        },
      },
      "Something went wrong on our side. Please try again in a minute.",
    ],
    ["sign_in_required", { status: 401, body: { error: "sign_in_required" } }, "Sign in again to team up."],
    ["forbidden", { status: 403, body: { error: "forbidden" } }, "Sign in again to team up."],
    [
      "worker_error",
      worker(502, "worker_error", "Something went wrong. Please try again."),
      "Something went wrong. Please try again.",
    ],
    ["a body that is not JSON", { status: 500, raw: "<html>" }, "Something went wrong. Please try again."],
    ["no connection", { offline: true }, "Check your connection, then try again."],
  ];

  it.each(cases)(
    "C-SHEET-TEAMUP error %s: shown on the sheet, nothing changes step",
    async (_name, answer, message) => {
      routes[U.send()] = answer;
      const { onSent } = await render();
      await click(sendButton());
      expect(alerts()).toEqual([message]);
      expect(note()).not.toBeNull();
      expect(onSent).not.toHaveBeenCalled();
      expect(sendButton().getAttribute("aria-busy")).toBeNull();
    },
  );

  it("C-SHEET-TEAMUP error note_too_short: under the note, which is marked invalid and takes focus; typing clears it", async () => {
    routes[U.send()] = worker(422, "note_too_short", "Add a little more: at least 30 characters.", "note");
    await render();
    (document.activeElement as HTMLElement).blur();
    await click(sendButton());
    const msg = dialog()!.querySelector('[role="alert"]')!;
    expect(text(msg)).toBe("Add a little more: at least 30 characters.");
    expect(note().getAttribute("aria-invalid")).toBe("true");
    expect(byIds(note().getAttribute("aria-describedby"))).toBe("Add a little more: at least 30 characters.");
    expect(document.activeElement).toBe(note());
    await type(NOTE);
    expect(note().getAttribute("aria-invalid")).toBeNull();
    expect(alerts()).toEqual([]);
  });

  it("C-SHEET-TEAMUP error brought_invalid: under Bring your ideas along", async () => {
    routes[U.send()] = worker(
      422,
      "brought_invalid",
      "Choose from your own shared ideas.",
      "brought_idea_ids",
    );
    await render();
    await click(sendButton());
    const msg = dialog()!.querySelector('[role="alert"]')!;
    expect(text(msg)).toBe("Choose from your own shared ideas.");
    expect(msg.closest(".tus-sec")!.querySelector(".dd")).not.toBeNull();
    expect(note().getAttribute("aria-invalid")).toBeNull();
  });

  it("C-SHEET-TEAMUP error draft_closed on Check it: This draft has already been sent.", async () => {
    routes[U.merge()] = worker(409, "draft_closed", "This draft has already been sent.");
    await render({ draftId: DRAFT });
    await click(radio("Ask Ravi to merge mine in"));
    await click(sendButton());
    expect(alerts()).toEqual(["This draft has already been sent."]);
  });

  it("C-SHEET-TEAMUP: a note that did not load says why, and Try again loads it", async () => {
    routes[U.note()] = {
      status: 404,
      body: { error: { code: "not_found", message: "We couldn’t find that." } },
    };
    await render();
    expect(nameOf(dialog()!)).toBe("Team up with Ravi");
    expect(alerts()).toEqual(["We couldn’t find that."]);
    expect(byIds(dialog()!.getAttribute("aria-describedby"))).toBe("We couldn’t find that.");
    let release!: () => void;
    routes[U.note()] = { body: drafted(), wait: new Promise<void>((r) => (release = r)) };
    const retry = button("Try again")!;
    await act(async () => retry.click());
    expect(dialog()!.getAttribute("aria-busy")).toBe("true");
    await act(async () => release());
    await settle();
    expect(note().value).toBe(DRAFTED);
    expect(document.activeElement).toBe(note());
  });

  it("C-SHEET-TEAMUP: neither read answers: the sheet says so with its own title", async () => {
    routes[U.mine()] = { offline: true };
    routes[U.note()] = { offline: true };
    await render();
    expect(nameOf(dialog()!)).toBe("Team up");
    expect(alerts()).toEqual(["Check your connection, then try again."]);
  });

  it.each([
    ["the lead", { me: "lead", why_not: "already_on_crew" }, "You lead this idea."],
    ["on the crew", { me: "member", why_not: "already_on_crew" }, "You’re on the crew."],
    ["a closed idea", { me: null, why_not: "idea_closed" }, "This idea is no longer open to team up."],
  ])(
    "C-SHEET-TEAMUP, L-TEAMUP.rules/1: %s: the sheet says so and nothing can be sent",
    async (_n, state, line) => {
      routes[U.mine()] = { body: { ...free(), ...state, can_request: false } };
      const { onClose } = await render();
      expect(nameOf(dialog()!)).toBe("Team up with Ravi");
      expect(byIds(dialog()!.getAttribute("aria-describedby"))).toBe(line);
      expect(button("Send to Ravi")).toBeUndefined();
      await click(button("Done"));
      expect(onClose).toHaveBeenCalledTimes(1);
    },
  );

  it("C-SHEET-TEAMUP errorFrom: the worker's shape, the proxy's banners and bare codes", () => {
    expect(errorFrom(422, { error: { code: "note_too_short", message: "m", field: "note" } })).toEqual({
      code: "note_too_short",
      message: "m",
      field: "note",
    });
    expect(errorFrom(404, { error: { code: "not_found", message: "" } }).message).toBe(
      "We couldn’t find that.",
    );
    expect(errorFrom(404, { error: "not_found" }).message).toBe("We couldn’t find that.");
    expect(errorFrom(404, null).message).toBe("We couldn’t find that.");
    expect(errorFrom(403, { error: "privacy_notice_required" }).message).toBe("Sign in again to team up.");
    expect(errorFrom(500, null)).toEqual({
      code: "error",
      message: "Something went wrong. Please try again.",
    });
  });
});

describe("C-SHEET-TEAMUP.a11y (WCAG 2.1 AA, F-MOTION.focus)", () => {
  it("C-SHEET-TEAMUP.a11y: renders nothing when closed, and at the page root (a portal) when open", async () => {
    await render({ open: false });
    expect(dialog()).toBeNull();
    expect(calls).toHaveLength(0);
    await render({ open: true });
    expect(host.contains(dialog())).toBe(false);
    expect(dialog()!.closest(".tus-wrap")!.parentElement).toBe(document.body);
  });

  it("C-SHEET-TEAMUP.a11y: Escape closes without sending, and focus returns to the opener", async () => {
    const { log, opener } = await openFromHarness();
    expect(document.activeElement).toBe(note());
    await press("Escape");
    expect(log).toEqual(["close"]);
    expect(dialog()).toBeNull();
    expect(posts()).toHaveLength(0);
    expect(document.activeElement).toBe(opener);
  });

  it("C-SHEET-TEAMUP.a11y: the cross and the backdrop close without sending; a click inside does not", async () => {
    let r = await render();
    await click(dialog()!.querySelector<HTMLElement>(".tus-h")!);
    expect(r.onClose).not.toHaveBeenCalled();
    await click(button("Close without sending"));
    expect(r.onClose).toHaveBeenCalledTimes(1);

    await act(async () => root.render(createElement("div")));
    r = await render();
    await click(document.querySelector<HTMLElement>(".tus-back")!);
    expect(r.onClose).toHaveBeenCalledTimes(1);
    expect(posts()).toHaveLength(0);
  });

  it("C-SHEET-TEAMUP.a11y: Tab and Shift+Tab stay inside the sheet; focus that lands outside is brought back", async () => {
    const { opener } = await openFromHarness();
    const close = button("Close without sending")!;
    await act(async () => sendButton().focus());
    await press("Tab");
    expect(document.activeElement).toBe(close);
    await press("Tab", { shiftKey: true });
    expect(document.activeElement).toBe(sendButton());
    await act(async () => opener.focus());
    expect(dialog()!.contains(document.activeElement)).toBe(true);
  });

  it("C-SHEET-TEAMUP.a11y, C-DROPDOWN/5: Escape in the open list closes the list only", async () => {
    const { log } = await openFromHarness();
    const field = button("Bring your ideas along: None picked")!;
    await act(async () => field.focus());
    await click(field);
    expect(field.getAttribute("aria-expanded")).toBe("true");
    await act(async () => checkbox(OWN[0]!.title).focus());
    await press("Escape");
    expect(field.getAttribute("aria-expanded")).toBe("false");
    expect(dialog()).not.toBeNull();
    expect(log).toEqual([]);
  });

  it("C-SHEET-TEAMUP.a11y: what was typed is kept when the sheet is reopened in the same session; sending clears it", async () => {
    routes[U.send()] = (b) => ({ status: 201, body: request((b as { note: string }).note) });
    const { opener } = await openFromHarness();
    await type(NOTE);
    await click(button("Bring your ideas along: None picked"));
    await click(checkbox(OWN[1]!.title));
    await press("Escape"); // closes the list
    await press("Escape"); // closes the sheet
    expect(dialog()).toBeNull();

    await click(opener);
    expect(note().value).toBe(NOTE);
    expect(text(dialog())).toContain("Looks good.");
    expect(button(`Bring your ideas along: ${OWN[1]!.title}`)).toBeDefined();
    await click(sendButton());
    await click(button("Done"));

    routes[U.mine()] = { body: free() }; // say Ravi has answered since: Team up again starts from the drafted note
    await click(opener);
    expect(note().value).toBe(DRAFTED);
    expect(button("Bring your ideas along: None picked")).toBeDefined();
  });
});

describe("C-SHEET-TEAMUP host helper and words", () => {
  it("C-SHEET-TEAMUP useTeamUpSheet: open(ideaId) mounts the sheet; Done closes it; onSent reaches the host", async () => {
    routes[U.send()] = { status: 201, body: request(DRAFTED) };
    const seen: string[] = [];
    function Host() {
      const teamUp = useTeamUpSheet({
        onSent: (s) => seen.push(`sent ${s.id}`),
        onClose: () => seen.push("closed"),
      });
      return createElement(
        "main",
        null,
        createElement(
          "button",
          { type: "button", id: "tile", onClick: () => teamUp.open(IDEA) },
          `Team up on ${TITLE}`,
        ),
        teamUp.sheet,
      );
    }
    await act(async () => root.render(createElement(Host)));
    expect(dialog()).toBeNull();
    const tile = document.getElementById("tile") as HTMLButtonElement;
    tile.focus();
    await click(tile);
    expect(nameOf(dialog()!)).toBe("Team up with Ravi");
    await click(sendButton());
    await click(button("Done"));
    expect(dialog()).toBeNull();
    expect(seen).toEqual(["sent req-1", "closed"]);
    expect(document.activeElement).toBe(tile);
  });

  it("C-SHEET-TEAMUP copy, BLD-E008: no gendered pronoun for a real person in any line", () => {
    const lines: string[] = [];
    for (const [k, v] of Object.entries(TEAMUP_COPY)) {
      if (typeof v === "string") lines.push(v);
      else if (k === "bringing") lines.push(TEAMUP_COPY.bringing(["A", "B"]));
      else if (typeof v === "function") {
        const f = v as (...a: unknown[]) => string;
        lines.push(f("Ravi", "Rejection SMS codes"), f("Ravi", 0), f("Ravi", 1), f("Ravi", 2), f(30), f(600));
      }
    }
    for (const line of lines) expect(line).not.toMatch(/\b(she|her|hers|herself|he|him|his|himself)\b/i);
  });

  it("C-SHEET-TEAMUP helpers: the hint, and Bringing “A”, “B” and “C”", () => {
    expect(noteHint(DRAFTED, DRAFTED, 30, 600).kind).toBe("drafted");
    expect(noteHint(NOTE, DRAFTED, 30, 600)).toEqual({ kind: "good", text: "Looks good.", ok: true });
    expect(noteHint("   short   ", DRAFTED, 30, 600).ok).toBe(false);
    expect(quotedList(["A"])).toBe("“A”");
    expect(quotedList(["A", "B"])).toBe("“A” and “B”");
    expect(quotedList(["A", "B", "C"])).toBe("“A”, “B” and “C”");
    expect(TEAMUP_COPY.bringing(["A", "B"])).toBe("Bringing “A” and “B”");
  });
});

describe("C-SHEET-TEAMUP review fixes (BLD-F074)", () => {
  it("C-SHEET-TEAMUP.sent: a reply without a request id shows no Withdraw, only the way on", async () => {
    routes[U.send()] = { status: 201, body: {} };
    const { onClose } = await render();
    await click(sendButton());
    expect(text(dialog())).toContain("Sent to Ravi");
    expect(button("Withdraw request")).toBeUndefined();
    await click(button("Done"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("C-SHEET-TEAMUP, L-TEAMUP.rules/4: still waiting but no request came back: Waiting for Ravi, and nothing to send", async () => {
    routes[U.mine()] = {
      body: { ...free(), can_request: false, why_not: "already_requested", request: null, after: WAITING },
    };
    await render();
    expect(byIds(dialog()!.getAttribute("aria-describedby"))).toBe("Waiting for Ravi");
    expect(button("Send to Ravi")).toBeUndefined();
    routes[U.mine()] = { body: { ...free(), can_request: false, why_not: "already_requested" } };
    await act(async () => root.render(createElement("div")));
    await render();
    expect(byIds(dialog()!.getAttribute("aria-describedby"))).toBe(TEAMUP_COPY.waiting("Ravi"));
  });

  /** A host that re-draws its "Team up" button as "Waiting for Ravi" with Withdraw once the request is sent. */
  function Redrawing(props: { mark: boolean; log: string[] }) {
    const [open, setOpen] = useState(false);
    const [sent, setSent] = useState(false);
    return createElement(
      "main",
      null,
      sent
        ? createElement(
            "p",
            null,
            "Waiting for Ravi ",
            createElement(
              "button",
              { type: "button", id: "withdraw", ...(props.mark ? teamUpOpener(IDEA) : {}) },
              "Withdraw",
            ),
          )
        : createElement("button", { type: "button", id: "opener", onClick: () => setOpen(true) }, "Team up"),
      createElement("button", { type: "button", id: "elsewhere" }, "Ideas close to yours"),
      createElement(TeamUpSheet, {
        ideaId: IDEA,
        open,
        onSent: () => setSent(true),
        onClose: () => {
          props.log.push("close");
          setOpen(false);
        },
        returnFocus: props.mark ? undefined : () => document.getElementById("elsewhere"),
      }),
    );
  }

  it("C-SHEET-TEAMUP.a11y, WCAG 2.4.3: the host re-draws the opener; focus returns to what it marks in its place", async () => {
    routes[U.send()] = { status: 201, body: request(DRAFTED) };
    const log: string[] = [];
    await act(async () => root.render(createElement(Redrawing, { mark: true, log })));
    const opener = document.getElementById("opener") as HTMLButtonElement;
    opener.focus();
    await click(opener);
    await click(sendButton());
    expect(document.getElementById("opener")).toBeNull(); // the host re-drew it while the sheet was open
    await click(button("Done"));
    expect(log).toEqual(["close"]);
    expect(document.activeElement).toBe(document.getElementById("withdraw"));
  });

  it("C-SHEET-TEAMUP.a11y, WCAG 2.4.3: with no mark, focus goes where the host's returnFocus says", async () => {
    routes[U.send()] = { status: 201, body: request(DRAFTED) };
    await act(async () => root.render(createElement(Redrawing, { mark: false, log: [] })));
    const opener = document.getElementById("opener") as HTMLButtonElement;
    opener.focus();
    await click(opener);
    await click(sendButton());
    await press("Escape");
    await settle();
    expect(document.activeElement).toBe(document.getElementById("elsewhere"));
  });

  it("C-SHEET-TEAMUP.a11y: what one person typed is never shown to the next person signed in on the page", async () => {
    const { opener } = await openFromHarness();
    await type(NOTE);
    await press("Escape");

    routes[U.me] = { body: ME_ARJUN };
    await click(opener);
    expect(note().value).toBe(DRAFTED);
    await press("Escape");

    routes[U.me] = { body: ME_KAVYA }; // Kavya again: what Kavya typed went when Arjun signed in
    await click(opener);
    expect(note().value).toBe(DRAFTED);
    await type(NOTE);
    await press("Escape");

    routes[U.me] = { status: 401, body: { error: "sign_in_required" } }; // not known: nothing is restored
    await click(opener);
    expect(note().value).toBe(DRAFTED);
  });
});

describe("C-SHEET-TEAMUP, a lead who is not named (BLD-F029, DEC-104)", () => {
  /** Lane C's hidden person, as the API sends a lead who hid their name from the Wall or has left. */
  const HIDDEN = { id: "p0a1b2c3d4e5f", name: "A colleague", first_name: "A colleague", initials: "" };
  const HIDDEN_WAITING = {
    state: "waiting",
    line: "Waiting for the lead",
    detail: "The lead reads your note, then approves or declines. You’ll hear in your Inbox.",
    action: { label: "Withdraw", op: "withdraw" },
  };
  beforeEach(() => {
    routes[U.mine()] = { body: { ...free(), lead: HIDDEN } };
    routes[U.note()] = { body: { ...drafted(), lead: HIDDEN } };
  });

  it("leadWord: the first name, or the lead for lane C's hidden person; nothing before a load", () => {
    expect(leadWord(RAVI)).toBe("Ravi");
    expect(leadWord({ name: "Ravi Nair", first_name: "", initials: "RN" })).toBe("Ravi Nair");
    expect(leadWord(HIDDEN)).toBe("the lead");
    expect(leadWord({ ...HIDDEN, initials: "AC" })).toBe("the lead");
    expect(leadWord(undefined)).toBe("");
  });

  it("C-SHEET-TEAMUP.compose: Team up with the lead, the line, the note's label, the privacy line, Send to the lead", async () => {
    await render();
    const d = dialog()!;
    expect(nameOf(d)).toBe("Team up with the lead");
    expect(byIds(d.getAttribute("aria-describedby"))).toBe(
      `The lead of “${TITLE}” decides who joins. Tell them what you bring.`,
    );
    expect(nameOf(note())).toBe("Your note to the lead");
    expect(text(d)).toContain("The lead sees your name, your note.");
    expect(button("Send to the lead")).toBeDefined();
    // The lead's disc has no initials to show; the pair stays decorative.
    expect(Array.from(d.querySelectorAll(".tus-pair .av")).map(text)).toEqual(["KI", ""]);
    expect(text(d)).not.toContain("A colleague");
  });

  it("C-SHEET-TEAMUP.sent: Sent to the lead, and the lead reads your note", async () => {
    routes[U.send()] = (b) => ({
      status: 201,
      body: { ...request((b as { note: string }).note), after: HIDDEN_WAITING },
    });
    const { onSent } = await render();
    await type(NOTE);
    await click(button("Send to the lead"));
    const d = dialog()!;
    expect(nameOf(d)).toBe("Team up with the lead");
    const status = d.querySelector('[role="status"]')!;
    expect(text(status)).toContain("Sent to the lead");
    expect(byIds(d.getAttribute("aria-describedby"))).toBe(
      "The lead reads your note, then approves or declines. You’ll hear in your Inbox.",
    );
    expect(onSent.mock.calls[0]![0]).toMatchObject({ after: { line: "Waiting for the lead" } });
    expect(text(d)).not.toContain("A colleague");
  });

  it("C-SHEET-TEAMUP Check it: Ask the lead to merge mine in, and the lead decides", async () => {
    await render({ draftId: DRAFT });
    const merge = radio("Ask the lead to merge mine in")!;
    expect(nameOf(merge)).toBe("Ask the lead to merge mine in");
    expect(byIds(merge.getAttribute("aria-describedby"))).toBe(
      "The lead decides. If the lead accepts, yours joins that idea with credit to you. If not, you send yours on its own.",
    );
    await click(merge);
    expect(text(dialog())).toContain("The lead sees your name, your note and the idea you bring.");
  });

  it("C-SHEET-TEAMUP, L-TEAMUP.rules/4: still waiting with no request back reads Waiting for the lead", async () => {
    routes[U.mine()] = {
      body: { ...free(), lead: HIDDEN, can_request: false, why_not: "already_requested" },
    };
    await render();
    expect(nameOf(dialog()!)).toBe("Team up with the lead");
    expect(byIds(dialog()!.getAttribute("aria-describedby"))).toBe("Waiting for the lead");
    expect(button("Send to the lead")).toBeUndefined();
  });

  it("C-SHEET-TEAMUP copy: every line with the lead reads as a sentence", () => {
    const lead = leadWord(HIDDEN);
    expect(TEAMUP_COPY.title(lead)).toBe("Team up with the lead");
    expect(TEAMUP_COPY.send(lead)).toBe("Send to the lead");
    expect(TEAMUP_COPY.sentTitle(lead)).toBe("Sent to the lead");
    expect(TEAMUP_COPY.waiting(lead)).toBe("Waiting for the lead");
    expect(TEAMUP_COPY.merge(lead)).toBe("Ask the lead to merge mine in");
    expect(TEAMUP_COPY.privacy(lead, 2)).toBe("The lead sees your name, your note and the ideas you bring.");
    // A named lead keeps the board's words.
    expect(TEAMUP_COPY.line("Ravi", TITLE)).toBe(
      `Ravi leads “${TITLE}” and decides who joins. Tell Ravi what you bring.`,
    );
    expect(TEAMUP_COPY.sentLine("Ravi")).toBe(
      "Ravi reads your note, then approves or declines. You’ll hear in your Inbox.",
    );
  });
});

describe("V-ACC.teamup/1 on the sheet (J-TEAMUP/2)", () => {
  /** Every control in the dialog a person could press: buttons, links and anything playing a button. */
  const pressable = () =>
    Array.from(dialog()!.querySelectorAll<HTMLElement>("button, a[href], [role='button'], [role='link']"));
  /** The cross closes and a dropdown's field opens a list; neither is an action. */
  const actions = () =>
    pressable().filter((el) => nameOf(el) !== "Close without sending" && !el.hasAttribute("aria-expanded"));

  it("V-ACC.teamup/1: on open the note is pre-filled, Bring your ideas along is collapsed at None picked, and the one action is Send to Ravi beside the close cross; no Cancel", async () => {
    await render();
    expect(note().value).toBe(DRAFTED);
    const field = button("Bring your ideas along: None picked")!;
    expect(field.getAttribute("aria-expanded")).toBe("false");
    expect(actions().map(nameOf)).toEqual(["Send to Ravi"]);
    expect(pressable().filter((el) => nameOf(el) === "Close without sending")).toHaveLength(1);
    expect(
      pressable()
        .map(nameOf)
        .filter((n) => /cancel/i.test(n)),
    ).toEqual([]);
    expect(text(dialog())).not.toMatch(/\bcancel\b/i);
  });

  it("V-ACC.teamup/1: opened from Check it, the choice replaces the dropdown and the one action is still Send to Ravi; no Cancel", async () => {
    await render({ draftId: DRAFT });
    expect(note().value).toBe(DRAFTED);
    expect(actions().map(nameOf)).toEqual(["Send to Ravi"]);
    expect(pressable().filter((el) => nameOf(el) === "Close without sending")).toHaveLength(1);
    expect(text(dialog())).not.toMatch(/\bcancel\b/i);
  });
});
