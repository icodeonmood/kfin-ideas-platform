"use client";

/**
 * C-LISTEN: "Listen to the whole idea" on the reviewer's page (S-R2.left/1). The browser reads the masked script
 * part by part with a local voice (BLD-B230): nothing leaves the device. The player is not shown when the browser
 * has no local English voice, or when Listen is switched off (desk.listen).
 */
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import type { ListenAudioResponse } from "@/lib/contracts";
import {
  clock,
  forgetOffline,
  jumpLabel,
  ListenEngine,
  LISTEN_ERROR,
  loadOffline,
  nowLabel,
  pickVoice,
  playLabel,
  progressLabel,
  saveOffline,
  type ListenScript,
  type ListenState,
  type ListenVoice,
} from "@/lib/desk/listen";

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

export function ListenPlayer({ ideaId, decided }: { ideaId: string; decided: boolean }) {
  const voice = useLocalVoice();
  const [script, setScript] = useState<ListenScript | null>(null);
  const [failed, setFailed] = useState(false);
  const [paused, setPaused] = useState(false); // switched off: the player is not shown
  const [player, setPlayer] = useState<{ engine: ListenEngine; state: ListenState } | null>(null);
  const [saved, setSaved] = useState(false);
  const [menu, setMenu] = useState(false);

  useEffect(() => {
    const store = storage();
    if (decided && store) forgetOffline(ideaId, store); // L-LISTEN/5: kept until the idea is decided
    let gone = false;
    (async () => {
      try {
        const res = await fetch(`/api/desk/ideas/${encodeURIComponent(ideaId)}/listen`);
        if (res.status === 503) {
          if (!gone) setPaused(true);
          return;
        }
        if (!res.ok) throw new Error(String(res.status));
        const body = (await res.json()) as ListenAudioResponse;
        if (!gone) setScript(toScript(body));
      } catch {
        const kept = store ? loadOffline(ideaId, store) : null; // offline: the copy saved on this device
        if (gone) return;
        if (kept) {
          setScript(kept);
          setSaved(true);
        } else setFailed(true);
      }
    })();
    return () => {
      gone = true;
    };
  }, [ideaId, decided]);

  useEffect(() => {
    if (!script || !voice || typeof window === "undefined") return;
    const e = new ListenEngine({
      synth: window.speechSynthesis,
      Utterance: window.SpeechSynthesisUtterance as unknown as ConstructorParameters<
        typeof ListenEngine
      >[0]["Utterance"],
      script,
      voice,
    });
    const off = e.subscribe((state) => setPlayer({ engine: e, state }));
    return () => {
      off();
      e.dispose();
    };
  }, [script, voice]);

  const engine = player?.engine ?? null;
  const state = player?.state ?? null;
  const timeline = engine?.timeline ?? null;
  const titles = useMemo(
    () => Object.fromEntries((script?.parts ?? []).map((p) => [p.part, p.title])),
    [script],
  );

  if (voice === null || paused) return null;
  const total = state?.total ?? timeline?.total ?? 0;
  const position = state?.position ?? 0;
  const playing = state?.playing ?? false;
  const ready = Boolean(state && voice);

  return (
    <section className="listen panel" aria-label="Listen to the whole idea">
      <div className="lmid">
        <h2 className="listen-t">Listen to the whole idea</h2>
        <p className="meta listen-time">
          {playing ? <span className="eq" aria-hidden="true" /> : null}
          {clock(position)} / {clock(total)}
          {playing && state?.currentPart ? (
            <span className="listen-now"> {nowLabel(titles[state.currentPart] ?? "")}</span>
          ) : null}
        </p>
        {failed || state?.error ? (
          <p className="fmsg" role="alert">
            {LISTEN_ERROR}{" "}
            <button type="button" className="tb" onClick={() => window.location.reload()}>
              Try again
            </button>
          </p>
        ) : null}
      </div>

      <div className="lctl">
        <div className="lmenu">
          <button
            type="button"
            className="round-btn quiet"
            aria-expanded={menu}
            aria-controls={`listen-parts-${ideaId}`}
            aria-label="Parts of the idea"
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
            <ul className="lparts" id={`listen-parts-${ideaId}`}>
              {timeline.parts.map((p) => (
                <li key={p.part}>
                  <button
                    type="button"
                    onClick={() => {
                      engine?.jumpTo(p.part);
                      setMenu(false);
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
          disabled={!script}
          onClick={() => {
            const store = storage();
            if (script && store && saveOffline(ideaId, script, store)) setSaved(true);
          }}
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
            aria-label={playing ? "Pause" : playLabel(total)}
            disabled={!ready}
            onClick={() => engine?.toggle()}
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
