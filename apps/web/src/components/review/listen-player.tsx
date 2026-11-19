"use client";

/**
 * C-LISTEN: "Listen to the whole idea" on the reviewer's page (S-R2.left/1).
 *
 * The voice (DEC-108): lane C's hosted audio first, `GET /api/ideas/:id/listen/chapters` then the stream from
 * `GET /api/ideas/:id/listen` in an <audio> element. While the audio is being made (202) the player waits and asks
 * again. When that route answers 404 (not on main yet) or 503 (switched off), or anything else, the browser reads the
 * masked script with a local voice (BLD-B230), and nothing leaves the device. With neither, the player is not shown;
 * nor when Listen is switched off (desk.listen). Both voices sit behind the same controls (`ListenControls`).
 *
 * C-LISTEN.anatomy (BLD-B267): the strip is drawn at its full size from the first render, the server's included, so
 * the page does not move when the audio answers. Until then the title stands, the time keeps its line unseen, the
 * play button is announced as "Play the whole idea" but does nothing (`aria-disabled`, so it stays focusable), and
 * the parts menu, "Save for offline" and the line are disabled; the player then takes over in place.
 */
import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type KeyboardEvent } from "react";

import type { ListenAudioResponse } from "@/lib/contracts";
import {
  AudioEngine,
  clock,
  forgetOffline,
  jumpLabel,
  ListenEngine,
  LISTEN_ERROR,
  loadOffline,
  nowLabel,
  OFFLINE_DAYS,
  pickVoice,
  PLAY_NAME,
  playLabel,
  progressLabel,
  readChapters,
  refreshOffline,
  saveOffline,
  type HostedChapters,
  type ListenControls,
  type ListenScript,
  type ListenState,
  type ListenVoice,
} from "@/lib/desk/listen";

import "./listen.css";

/** While lane C's audio is being made (202), ask again this often, this many times, then use the browser's voice. */
const PENDING_MS = 3000;
const PENDING_TRIES = 8;
const AUDIO_CACHE = "listen-audio";
const DAY_MS = 86_400_000;

type Source =
  | { kind: "hosted"; chapters: HostedChapters; src: string; local: boolean }
  | { kind: "local"; script: ListenScript; version: string | null };

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

const noVoice = () => () => undefined;

function voiceSnapshot(): ListenVoice | null {
  return typeof window !== "undefined" && window.speechSynthesis
    ? pickVoice(window.speechSynthesis.getVoices())
    : null;
}

function voiceSubscribe(changed: () => void): () => void {
  const synth = window.speechSynthesis;
  if (!synth) return () => undefined;
  // Chrome loads its voice list late.
  synth.addEventListener("voiceschanged", changed);
  return () => synth.removeEventListener("voiceschanged", changed);
}

/** The best local English voice; undefined while the server renders, null when the browser has none. */
function useLocalVoice(): ListenVoice | null | undefined {
  return useSyncExternalStore(
    typeof window === "undefined" ? noVoice : voiceSubscribe,
    voiceSnapshot,
    () => undefined,
  );
}

const toScript = (r: ListenAudioResponse): ListenScript => ({
  parts: r.parts.map((p) => ({ part: p.part, title: p.title, text: p.text })),
});

const audioUrl = (ideaId: string) => `/api/ideas/${encodeURIComponent(ideaId)}/listen`;
const chaptersUrl = (ideaId: string) => `${audioUrl(ideaId)}/chapters`;
const wait = (ms: number) => new Promise((done) => setTimeout(done, ms));

// ---------------------------------------------------------------------------------------------------------------
// The hosted audio kept on this device (C-LISTEN.behaviour/4, L-LISTEN/5): the stream and its chapters in the
// browser's cache, removed when the idea is decided or after 30 days. Every step is optional: a browser without the
// cache, or one that refuses it, simply has nothing saved.

async function audioCache(): Promise<Cache | null> {
  try {
    return typeof caches === "undefined" ? null : await caches.open(AUDIO_CACHE);
  } catch {
    return null;
  }
}

async function saveHosted(ideaId: string, chapters: HostedChapters): Promise<boolean> {
  const cache = await audioCache();
  if (!cache) return false;
  try {
    const audio = await fetch(audioUrl(ideaId));
    if (!audio.ok) return false;
    await cache.put(audioUrl(ideaId), audio);
    await cache.put(
      chaptersUrl(ideaId),
      new Response(JSON.stringify(chapters), {
        headers: { "Content-Type": "application/json", "X-Saved-At": String(Date.now()) },
      }),
    );
    return true;
  } catch {
    return false;
  }
}

async function forgetHosted(ideaId: string): Promise<void> {
  const cache = await audioCache();
  try {
    await cache?.delete(audioUrl(ideaId));
    await cache?.delete(chaptersUrl(ideaId));
  } catch {
    // nothing kept
  }
}

/** The saved chapters, while they are fresh; a copy past 30 days is removed. */
async function savedChapters(ideaId: string): Promise<{ cache: Cache; chapters: HostedChapters } | null> {
  const cache = await audioCache();
  if (!cache) return null;
  try {
    const kept = await cache.match(chaptersUrl(ideaId));
    if (!kept) return null;
    const at = Number(kept.headers.get("X-Saved-At"));
    if (!at || Math.abs(Date.now() - at) > OFFLINE_DAYS * DAY_MS) {
      await forgetHosted(ideaId);
      return null;
    }
    const chapters = readChapters(await kept.json());
    return chapters ? { cache, chapters } : null;
  } catch {
    return null;
  }
}

/** Offline: the saved audio, played from this device. */
async function offlineHosted(ideaId: string): Promise<Source | null> {
  const saved = await savedChapters(ideaId);
  if (!saved) return null;
  try {
    const audio = await saved.cache.match(audioUrl(ideaId));
    if (!audio) return null;
    return {
      kind: "hosted",
      chapters: saved.chapters,
      src: URL.createObjectURL(await audio.blob()),
      local: true,
    };
  } catch {
    return null;
  }
}

/** Lane C's chapters, waiting while the audio is made; null means the browser's voice reads it (DEC-108). */
async function loadHosted(ideaId: string, gone: () => boolean): Promise<Source | null> {
  for (let tries = 0; tries < PENDING_TRIES; tries += 1) {
    let res: Response;
    try {
      res = await fetch(chaptersUrl(ideaId));
    } catch {
      return offlineHosted(ideaId);
    }
    if (gone()) return null;
    if (res.status === 202) {
      await wait(PENDING_MS);
      if (gone()) return null;
      continue;
    }
    if (!res.ok) return null; // 404 not on main yet, 503 switched off, or failed: the browser's voice
    const chapters = readChapters(await res.json().catch(() => null));
    return chapters ? { kind: "hosted", chapters, src: audioUrl(ideaId), local: false } : null;
  }
  return null;
}

export function ListenPlayer({ ideaId, decided }: { ideaId: string; decided: boolean }) {
  const voice = useLocalVoice();
  const [source, setSource] = useState<Source | null>(null);
  const [failed, setFailed] = useState(false);
  const [paused, setPaused] = useState(false); // switched off: the player is not shown
  const [player, setPlayer] = useState<{ engine: ListenControls; state: ListenState } | null>(null);
  const [saved, setSaved] = useState(false);
  const [menu, setMenu] = useState(false);
  // L-LISTEN/7: "Try again" prepares the audio again in place, never by reloading the page
  const [attempt, setAttempt] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const menuWrap = useRef<HTMLDivElement>(null);
  const menuList = useRef<HTMLUListElement>(null);

  useEffect(() => {
    const store = storage();
    if (decided) {
      if (store) forgetOffline(ideaId, store); // L-LISTEN/5: kept until the idea is decided
      void forgetHosted(ideaId);
    }
    let gone = false;
    let objectUrl: string | null = null;
    (async () => {
      const hosted = await loadHosted(ideaId, () => gone);
      if (gone) return;
      if (hosted?.kind === "hosted") {
        if (hosted.local) objectUrl = hosted.src;
        setSource(hosted);
        const kept = hosted.local || (await savedChapters(ideaId)) !== null;
        if (gone) return;
        setSaved(kept);
        // A saved copy is refreshed while online, so offline plays the idea as it is now (L-LISTEN/3)
        if (kept && !hosted.local) void saveHosted(ideaId, hosted.chapters);
        return;
      }
      try {
        const res = await fetch(`/api/desk/ideas/${encodeURIComponent(ideaId)}/listen`);
        if (res.status === 503) {
          if (!gone) setPaused(true);
          return;
        }
        if (!res.ok) throw new Error(String(res.status));
        const body = (await res.json()) as ListenAudioResponse;
        if (gone) return;
        const script = toScript(body);
        setSource({ kind: "local", script, version: body.version ?? null });
        // A copy saved at another version is replaced with this one
        setSaved(store && body.version ? refreshOffline(ideaId, script, body.version, store) : false);
      } catch {
        const kept = store ? loadOffline(ideaId, store) : null; // offline: the copy saved on this device
        if (gone) return;
        if (kept) {
          setSource({ kind: "local", script: kept, version: null });
          setSaved(true);
        } else setFailed(true);
      }
    })();
    return () => {
      gone = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [ideaId, decided, attempt]);

  useEffect(() => {
    if (!source || typeof window === "undefined") return;
    let e: ListenControls;
    if (source.kind === "hosted") {
      if (!audioRef.current) return;
      e = new AudioEngine({ audio: audioRef.current, chapters: source.chapters });
    } else {
      if (!voice) return;
      e = new ListenEngine({
        synth: window.speechSynthesis,
        Utterance: window.SpeechSynthesisUtterance as unknown as ConstructorParameters<
          typeof ListenEngine
        >[0]["Utterance"],
        script: source.script,
        voice,
      });
    }
    const off = e.subscribe((state) => setPlayer({ engine: e, state }));
    return () => {
      off();
      e.dispose();
    };
  }, [source, voice]);

  // The parts menu takes focus on its first item, and closes on a click anywhere outside it
  useEffect(() => {
    if (!menu) return;
    menuList.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const outside = (ev: PointerEvent) => {
      if (!menuWrap.current?.contains(ev.target as Node)) setMenu(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [menu]);

  const engine = player?.engine ?? null;
  const state = player?.state ?? null;
  const timeline = engine?.timeline ?? null;
  const titles = useMemo(
    () => Object.fromEntries((timeline?.parts ?? []).map((p) => [p.part, p.title])),
    [timeline],
  );

  if (paused) return null;
  // The browser's voice is needed only once its script is the source; until a source answers, the strip stands
  if (source?.kind === "local" && voice === null) return null;
  const total = state?.total ?? timeline?.total ?? 0;
  const position = state?.position ?? 0;
  const playing = state?.playing ?? false;
  const ready = Boolean(state);

  function closeMenu() {
    setMenu(false);
    menuButton.current?.focus();
  }

  /** The menu's keys: arrows, Home and End move; Escape closes it back to its button; Tab leaves it closed. */
  function menuKeys(ev: KeyboardEvent<HTMLUListElement>) {
    const items = [...(menuList.current?.querySelectorAll<HTMLButtonElement>("button") ?? [])];
    const at = items.findIndex((b) => b === document.activeElement);
    const go = (i: number) => items[(i + items.length) % items.length]?.focus();
    const keys: Record<string, () => void> = {
      Escape: closeMenu,
      ArrowDown: () => go(at + 1),
      ArrowUp: () => go(at - 1),
      Home: () => go(0),
      End: () => go(items.length - 1),
    };
    if (ev.key === "Tab") setMenu(false);
    const act = keys[ev.key];
    if (act) {
      ev.preventDefault();
      act();
    }
  }

  async function saveForOffline() {
    if (source?.kind === "hosted") {
      if (await saveHosted(ideaId, source.chapters)) setSaved(true);
      return;
    }
    const store = storage();
    if (source && store && saveOffline(ideaId, source.script, store, Date.now(), source.version))
      setSaved(true);
  }

  return (
    <section className="listen panel" aria-labelledby={`listen-t-${ideaId}`}>
      {source?.kind === "hosted" ? <audio ref={audioRef} src={source.src} preload="metadata" hidden /> : null}
      <div className="lmid">
        <h2 id={`listen-t-${ideaId}`} className="listen-t" ref={titleRef} tabIndex={-1}>
          Listen to the whole idea
        </h2>
        {/* Its line is kept, unseen, until the length is known: no "0:00 / 0:00" and no new words (BLD-B267) */}
        <p className={`meta listen-time${ready ? "" : " listen-wait"}`}>
          {playing ? <span className="eq" aria-hidden="true" /> : null}
          {clock(position)} / {clock(total)}
          {playing && state?.currentPart ? (
            <span className="listen-now"> {nowLabel(titles[state.currentPart] ?? "")}</span>
          ) : null}
        </p>
        {failed || state?.error ? (
          <p className="fmsg" role="alert">
            {LISTEN_ERROR}{" "}
            <button
              type="button"
              className="tb"
              onClick={() => {
                setFailed(false);
                setPlayer(null);
                setSource(null);
                setAttempt((n) => n + 1);
                titleRef.current?.focus();
              }}
            >
              Try again
            </button>
          </p>
        ) : null}
      </div>

      <div className="lctl">
        <div className="lmenu" ref={menuWrap}>
          <button
            ref={menuButton}
            type="button"
            className="round-btn quiet"
            aria-haspopup="menu"
            aria-expanded={menu}
            aria-controls={menu ? `listen-parts-${ideaId}` : undefined}
            aria-label="Jump to a part"
            disabled={!ready}
            onClick={() => setMenu((m) => !m)}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <path
                d="M3 5h12M3 9h12M3 13h12"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
            </svg>
          </button>
          {menu && timeline ? (
            <ul
              ref={menuList}
              className="lparts"
              id={`listen-parts-${ideaId}`}
              role="menu"
              aria-label="Jump to a part"
              onKeyDown={menuKeys}
            >
              {timeline.parts.map((p) => (
                <li key={p.part} role="none">
                  <button
                    type="button"
                    role="menuitem"
                    tabIndex={-1}
                    onClick={() => {
                      engine?.jumpTo(p.part);
                      closeMenu();
                    }}
                  >
                    {jumpLabel(p.title, p.start)}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <button
          type="button"
          className="round-btn quiet"
          aria-label={saved ? "Saved for offline" : "Save for offline"}
          aria-pressed={saved}
          disabled={!source}
          onClick={() => void saveForOffline()}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth="1.5" fill="none" />
            <path d="M9 5.5v6M6.5 9.5 9 12l2.5-2.5" stroke="currentColor" strokeWidth="1.5" fill="none" />
          </svg>
          <span className="vh">{saved ? "Saved for offline" : "Save for offline"}</span>
        </button>
        <div className="lplay-wrap">
          <button
            type="button"
            className="lplay"
            aria-label={playing ? "Pause" : ready ? playLabel(total) : PLAY_NAME}
            // Not `disabled`: it stays focusable and announced before the audio answers, and ignores clicks and keys
            aria-disabled={ready ? undefined : true}
            onClick={() => {
              if (ready) engine?.toggle();
            }}
          >
            {playing ? (
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path d="M6 4v10M12 4v10" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path d="M6 3.5v11l9-5.5z" fill="currentColor" />
              </svg>
            )}
          </button>
          {playing ? (
            <button
              type="button"
              className="lspeed"
              aria-label={`Speed ${state?.rate ?? 1} times`}
              onClick={() => engine?.cycleSpeed()}
            >
              {state?.rate ?? 1}×
            </button>
          ) : null}
        </div>
      </div>

      <div className="lchap">
        <input
          type="range"
          className="lline"
          min={0}
          max={Math.max(1, Math.round(total))}
          step={1}
          value={Math.round(position)}
          aria-label="Position in the idea"
          aria-valuetext={progressLabel(position, total)}
          disabled={!ready}
          onChange={(e) => engine?.seek(Number(e.target.value))}
          style={{ ["--played" as string]: total ? `${(position / total) * 100}%` : "0%" }}
        />
        <span className="lticks" aria-hidden="true">
          {timeline?.parts.slice(1).map((p) => (
            <i key={p.part} style={{ left: `${(p.start / (timeline.total || 1)) * 100}%` }} />
          ))}
        </span>
      </div>
    </section>
  );
}
