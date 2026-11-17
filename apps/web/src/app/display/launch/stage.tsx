"use client";

/**
 * S-LAUNCH (L-DISPLAY.launch): three frames. Before Start, the operator's instructions, Start, Full screen and the
 * six beats. Start plays the fixed 30-second reveal with sound: 0:00 black and the bell; 0:04 the spark rises; 0:08
 * the two zeros arrive; 0:14 "1% Club"; 0:16 the tagline; then the QR frame draws so the invitation lands at 0:30
 * and stays. Escape only leaves full screen (the browser's own key), so the sequence carries on; a reload returns
 * to the operator frame (S-LAUNCH/6). With reduced motion the final frame shows at once, with the bell only.
 */
import { Fragment, useCallback, useEffect, useRef, useState, type CSSProperties } from "react";

import { fullScreen, prefersReducedMotion, useDisplaySurface } from "../surface";
import { playSignature } from "./sound";

/** When each beat starts, from Start. The QR frame draws from 0:29 so the invitation's words land at 0:30. */
export const STEP_AT_MS = [0, 4000, 8000, 14000, 16000, 29000] as const;
const FINAL = STEP_AT_MS.length - 1;

const BEATS: [string, string][] = [
  ["0:00", "Black, and the bell"],
  ["0:04", "The spark rises"],
  ["0:08", "The two zeros arrive"],
  ["0:14", "1% Club"],
  ["0:16", "The tagline"],
  ["0:30", "The invitation and QR code stay"],
];

/** Said once as each part appears, then cleared, so the reading order never holds the same words twice. */
const ANNOUNCE = [
  "",
  "",
  "",
  "1% Club.",
  "1% Club. 1% spark. 99% sweat.",
  "You bring the spark. Scan the code to share your idea.",
];
const ANNOUNCE_FOR_MS = 2500;

type Props = { url: string; shownUrl: string; qr: { size: number; d: string } };

const on = (base: string, shown: boolean) => (shown ? `${base} is-on` : base);

/** A line whose words build one after another (`--j`), starting `delay` seconds after its beat. */
function Words({ text, delay = 0 }: { text: string; delay?: number }) {
  return text.split(" ").map((word, j) => (
    <Fragment key={j}>
      <span className="dl-wd" style={{ "--j": j, "--d": `${delay}s` } as CSSProperties}>
        {word}
      </span>{" "}
    </Fragment>
  ));
}

export function LaunchScreen({ url, shownUrl, qr }: Props) {
  const [step, setStep] = useState<number | null>(null);
  const [clearedStep, setClearedStep] = useState<number | null>(null);
  const timers = useRef<number[]>([]);
  const audio = useRef<AudioContext | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const startButton = useRef<HTMLButtonElement>(null);
  const started = step !== null;

  useDisplaySurface(root);

  const stop = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
    audio.current?.close().catch(() => undefined);
    audio.current = null;
  }, []);

  useEffect(() => stop, [stop]);

  // Focus starts on Start; once it is pressed the button is gone, so focus rests on the screen itself.
  useEffect(() => {
    if (started) root.current?.focus();
    else startButton.current?.focus();
  }, [started]);

  const fresh = step === null ? "" : (ANNOUNCE[step] ?? "");
  const announcement = clearedStep === step ? "" : fresh;
  useEffect(() => {
    if (!fresh) return;
    const t = window.setTimeout(() => setClearedStep(step), ANNOUNCE_FOR_MS);
    return () => window.clearTimeout(t);
  }, [step, fresh]);

  function start() {
    stop();
    setClearedStep(null);
    const reduced = prefersReducedMotion();
    if (typeof window.AudioContext === "function") {
      try {
        audio.current = new window.AudioContext();
        playSignature(audio.current, !reduced);
      } catch {
        audio.current = null; // if audio fails the visuals still play (L-DISPLAY.launch/4)
      }
    }
    if (reduced) {
      setStep(FINAL);
      return;
    }
    setStep(0);
    STEP_AT_MS.forEach((ms, i) => {
      if (i > 0) timers.current.push(window.setTimeout(() => setStep(i), ms));
    });
  }

  if (!started) {
    return (
      <div ref={root} className="dsp dl" tabIndex={-1}>
        <section className="dl-intro" aria-labelledby="dl-title">
          <p className="dl-eyebrow">1% Club · inauguration, Friday 20 November</p>
          <h1 id="dl-title" className="dl-title">
            Launch screen
          </h1>
          <div className="dl-lead">
            <p>
              For the lamp lighting on Friday 20 November. Put this page on the big screen, choose Full
              screen, then press Start the moment the lamp is lit.
            </p>
            <p>
              It runs for about thirty seconds, with a bell and a spark sound at the start, and then stays on
              the invitation and its QR code.
            </p>
          </div>
          <div className="dl-controls">
            <button ref={startButton} type="button" className="dl-btn dl-btn-white" onClick={start}>
              Start
            </button>
            <button type="button" className="dl-btn dl-btn-line" onClick={() => fullScreen(root.current)}>
              Full screen
            </button>
          </div>
          <ol className="dl-beats" aria-label="What plays after Start">
            {BEATS.map(([at, what]) => (
              <li key={at}>
                <p className="dl-beat-at">{at}</p>
                <p className="dl-beat-what">{what}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>
    );
  }

  const s = step;
  return (
    <div ref={root} className="dsp dl" tabIndex={-1} role="region" aria-label="Launch screen">
      <div className="dsp-stage dl-reveal" data-step={s}>
        <div className={on("dl-glow", s >= 1)} aria-hidden="true" />
        <div className="dl-grid">
          <div>
            <div className="dl-lockup">
              <svg className="dl-mark" viewBox="0 0 200 240" aria-hidden="true" focusable="false">
                <circle
                  className={on("dl-zero", s >= 2)}
                  cx="52"
                  cy="58"
                  r="34"
                  fill="none"
                  stroke="#FFFFFF"
                  strokeWidth="12"
                  pathLength={1}
                />
                <circle
                  className={on("dl-zero dl-zero-2", s >= 2)}
                  cx="148"
                  cy="184"
                  r="34"
                  fill="none"
                  stroke="#FFFFFF"
                  strokeWidth="12"
                  pathLength={1}
                />
                <polygon
                  className={on("dl-spark", s >= 1)}
                  points="34,236 146.9,27.2 169.1,40.8"
                  fill="#FF5B14"
                />
                <circle className={on("dl-ember", s >= 1)} cx="171.6" cy="11.8" r="8" fill="#FF5B14" />
              </svg>
              {/* Each part stays out of the reading order until its moment (review A3). */}
              <h1 className={on("dl-name", s >= 3)} aria-hidden={s < 3 ? true : undefined}>
                <Words text="1% Club" />
              </h1>
            </div>
            <p className={on("dl-tagline", s >= 4)} aria-hidden={s < 4 ? true : undefined}>
              <Words text="1% spark. 99% sweat." />
            </p>
          </div>
          <div className={on("dl-invite", s >= 5)} aria-hidden={s < 5 ? true : undefined}>
            <div className="dl-qr-frame">
              <svg
                className="dl-qr"
                viewBox={`-4 -4 ${qr.size + 8} ${qr.size + 8}`}
                role="img"
                aria-label={`QR code for ${url}`}
                shapeRendering="crispEdges"
              >
                <rect x="-4" y="-4" width={qr.size + 8} height={qr.size + 8} fill="#FFFFFF" />
                <path d={qr.d} fill="#0A0A0C" />
              </svg>
            </div>
            <p className="dl-invite-line">
              <Words text="You bring the spark." delay={1} />
            </p>
            <p className="dl-scan">
              <Words text="Scan the code to share your idea." delay={1.6} />
            </p>
            <p className="dl-url">{shownUrl}</p>
          </div>
        </div>
        <p className="dsp-vh" aria-live="polite">
          {announcement}
        </p>
      </div>
    </div>
  );
}
