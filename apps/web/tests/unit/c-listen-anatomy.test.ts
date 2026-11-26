// @vitest-environment jsdom
/**
 * C-LISTEN.anatomy on S-R2 (J-REVIEW/1, /4, /5, A1, A5, M3; BLD-B267): "Listen to the whole idea" is there at its
 * full size from the first render, the server's included, before lane C's audio or the desk's script answers. The
 * play button is focusable and announced as "Play the whole idea" but inert (`aria-disabled`, not `disabled`) until
 * the length is known; then the player takes over in place. Switched off (503), the strip goes. Mocked routes; the
 * idea is synthetic. jsdom has no speechSynthesis, so the hosted audio is the voice here.
 */
import { act, createElement } from "react";
import { createRoot, hydrateRoot, type Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ListenPlayer, VOICE_WAIT_MS } from "@/components/review/listen-player";
import { LISTEN_ERROR } from "@/lib/desk/listen";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const IDEA = "IDEA-2026-001412";
const CHAPTERS = `/api/ideas/${IDEA}/listen/chapters`;
const SCRIPT = `/api/desk/ideas/${IDEA}/listen`;
const BODY = {
  parts: [
    { part: "summary", start_s: 0 },
    { part: "often", start_s: 38 },
    { part: "who", start_s: 52 },
    { part: "cost", start_s: 70 },
    { part: "evidence", start_s: 95 },
    { part: "fix", start_s: 110 },
  ],
  duration_s: 130,
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

/** Each route answers only when the test says so. */
let pending: Map<string, (r: Response) => void>;
let calls: string[];
let host: HTMLDivElement;
let root: Root | null;

beforeEach(() => {
  pending = new Map();
  calls = [];
  host = document.createElement("div");
  document.body.append(host);
  root = null;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      (url: string) =>
        new Promise<Response>((answer) => {
          calls.push(url);
          pending.set(url, answer);
        }),
    ),
  );
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function settle() {
  for (let i = 0; i < 8; i++) await act(async () => await new Promise((done) => setTimeout(done, 0)));
}

async function answer(url: string, res: Response) {
  await settle();
  const send = pending.get(url);
  expect(send, url).toBeDefined();
  await act(async () => send!(res));
  await settle();
}

const player = () => createElement(ListenPlayer, { ideaId: IDEA, decided: false });
const play = (el: ParentNode = host) => el.querySelector<HTMLButtonElement>("button.lplay");
const title = (el: ParentNode = host) => el.querySelector(".listen-t")?.textContent;

describe("C-LISTEN.anatomy: the listen strip from the first paint", () => {
  it("C-LISTEN.anatomy before the audio answers: the server and the first client render draw the title and an inert, named play button", async () => {
    const server = renderToString(player());
    host.innerHTML = server;
    expect(title()).toBe("Listen to the whole idea");
    expect(play()?.getAttribute("aria-disabled")).toBe("true");
    expect(play()?.hasAttribute("disabled")).toBe(false);
    expect(play()?.getAttribute("aria-label")).toBe("Play the whole idea");
    // No new words: the time keeps its line unseen until the length is known
    expect(host.querySelector(".listen-time")?.classList.contains("listen-wait")).toBe(true);
    expect(host.textContent).not.toMatch(/Loading|Preparing/);

    await act(async () => {
      root = hydrateRoot(host, player());
    });
    await settle();
    expect(calls).toEqual([CHAPTERS]);
    const strip = host.querySelector("section.listen");
    expect(strip).not.toBeNull();
    expect(title()).toBe("Listen to the whole idea");
    const button = play()!;
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.getAttribute("aria-label")).toBe("Play the whole idea");
    // Focusable, and a click or a key does nothing
    button.focus();
    expect(document.activeElement).toBe(button);
    await act(async () => {
      button.click();
      button.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
      button.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
    });
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.getAttribute("aria-label")).toBe("Play the whole idea");
    // The parts menu and "Save for offline" are there and inert
    expect(host.querySelector<HTMLButtonElement>('[aria-label="Jump to a part"]')?.disabled).toBe(true);
    expect(host.querySelector<HTMLButtonElement>('[aria-label="Save for offline"]')?.disabled).toBe(true);
  });

  it("C-LISTEN.anatomy once the audio answers: the same strip, the play button enabled and named with the full length", async () => {
    await act(async () => {
      root = createRoot(host);
      root.render(player());
    });
    const strip = host.querySelector("section.listen");
    expect(strip).not.toBeNull();
    expect(play()?.getAttribute("aria-disabled")).toBe("true");
    await answer(CHAPTERS, json(200, BODY));
    // In place: the section drawn on the first paint is the one that plays
    expect(host.querySelector("section.listen")).toBe(strip);
    const button = play()!;
    expect(button.hasAttribute("aria-disabled")).toBe(false);
    expect(button.disabled).toBe(false);
    expect(button.getAttribute("aria-label")).toBe("Play the whole idea, 2 minutes 10 seconds");
    const time = host.querySelector(".listen-time")!;
    expect(time.classList.contains("listen-wait")).toBe(false);
    expect(time.textContent).toBe("0:00 / 2:10");
    expect(host.querySelector<HTMLButtonElement>('[aria-label="Jump to a part"]')?.disabled).toBe(false);
  });

  it("C-LISTEN.anatomy switched off (503): the strip goes, as before", async () => {
    await act(async () => {
      root = createRoot(host);
      root.render(player());
    });
    expect(title()).toBe("Listen to the whole idea");
    await answer(CHAPTERS, json(503, { error: { code: "switched_off" } }));
    await answer(SCRIPT, json(503, { error: { code: "switched_off" } }));
    expect(calls).toEqual([CHAPTERS, SCRIPT]);
    expect(host.innerHTML).toBe("");
  });
});

// J-REVIEW/M3 (BLD-B271): when lane C's audio routes answer 404 (as they did for a merged idea until
// `speech/listen.py` NOT_LISTENABLE dropped "merged"), the desk's script is the only source and the device's voice
// reads it. A browser without a local English voice (headless Chromium, the journeys' browser) dropped the strip.
const SCRIPT_BODY = {
  parts: [
    { part: "summary", title: "The problem", text: "Investors call the branch about a code.", seconds: 4 },
    { part: "often", title: "How often", text: "About 40 calls a day at one branch.", seconds: 3 },
    { part: "who", title: "Who it affects", text: "Investors.", seconds: 2 },
    { part: "cost", title: "What it’s worth", text: "Not worked out yet.", seconds: 2 },
    { part: "evidence", title: "Attached", text: "Nothing attached.", seconds: 2 },
    { part: "fix", title: "Fix", text: "No fix suggested. It was optional.", seconds: 3 },
  ],
  chapters: [],
  total_seconds: 16,
  version: "v-merged-1",
};

describe("J-REVIEW/M3, C-LISTEN: a merged idea's S-R2 keeps Listen", () => {
  it("J-REVIEW/M3, C-LISTEN: a merged idea's S-R2 keeps Listen with no device voice, then says it couldn’t prepare the audio (L-LISTEN/7)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      await act(async () => {
        root = createRoot(host);
        root.render(player());
      });
      await answer(CHAPTERS, json(404, { error: "not_found" }));
      await answer(SCRIPT, json(200, SCRIPT_BODY));
      expect(calls).toEqual([CHAPTERS, SCRIPT]);
      // The strip stays at its place, waiting for a voice: title, and the inert, named play button
      expect(host.querySelector("section.listen")).not.toBeNull();
      expect(title()).toBe("Listen to the whole idea");
      expect(play()?.getAttribute("aria-disabled")).toBe("true");
      expect(play()?.getAttribute("aria-label")).toBe("Play the whole idea");
      expect(host.querySelector('[role="alert"]')).toBeNull();
      expect(host.querySelector<HTMLButtonElement>('[aria-label="Save for offline"]')?.disabled).toBe(true);
      // No voice comes: the player's own failure line and Try again, in the strip; the page is unaffected
      await act(async () => {
        vi.advanceTimersByTime(VOICE_WAIT_MS);
      });
      await settle();
      expect(title()).toBe("Listen to the whole idea");
      expect(host.querySelector('[role="alert"]')?.textContent).toBe(`${LISTEN_ERROR} Try again`);
      expect(play()?.getAttribute("aria-disabled")).toBe("true");
    } finally {
      vi.useRealTimers();
    }
  });

  it("J-REVIEW/M3, C-LISTEN: with a device voice, a merged idea's strip plays its own script, named with its length", async () => {
    const voice = {
      name: "Synthetic en-IN",
      lang: "en-IN",
      localService: true,
      default: true,
      voiceURI: "syn",
    };
    vi.stubGlobal("speechSynthesis", {
      getVoices: () => [voice],
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      speak: () => undefined,
      cancel: () => undefined,
      pause: () => undefined,
      resume: () => undefined,
      speaking: false,
      paused: false,
      pending: false,
    });
    vi.stubGlobal(
      "SpeechSynthesisUtterance",
      class {
        constructor(public text: string) {}
      },
    );
    await act(async () => {
      root = createRoot(host);
      root.render(player());
    });
    await answer(CHAPTERS, json(404, { error: "not_found" }));
    await answer(SCRIPT, json(200, SCRIPT_BODY));
    const button = play()!;
    expect(button.hasAttribute("aria-disabled")).toBe(false);
    expect(button.getAttribute("aria-label")).toMatch(/^Play the whole idea, \d+ seconds?$/);
    expect(host.querySelector('[role="alert"]')).toBeNull();
  });
});
