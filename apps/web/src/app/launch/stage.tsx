"use client";

/**
 * The logo introduction for the lamp-lighting go-live (DEC-046, DEC-050, docs/BRAND.md section 5).
 * 0:00 black and the bell; 0:04 the spark rises with a soft crackle; 0:08 the two zeros arrive; 0:14 "1% Club";
 * 0:16 the tagline; 0:30 the QR code and "You bring the spark.", which then stays on screen.
 * The sound is synthesised here (Web Audio), only after the operator presses Start; there are no audio files.
 * With reduced motion the final frame shows at once.
 */
import { useCallback, useEffect, useRef, useState } from "react";

const STEP_AT_MS = [0, 4000, 8000, 14000, 16500, 30000];
const FINAL = STEP_AT_MS.length - 1;
const SPARK = "#F46835";
const CRACKLE_AT_S = 4;

type Props = { url: string; shownUrl: string; qr: { size: number; d: string } };

/**
 * One bell tone (a few inharmonic, decaying sine partials), then a soft crackle of short noise bursts. With reduced
 * motion the screen jumps to its last frame, so only the bell plays: no crackle over a still picture (review A4).
 */
function playSignature(ctx: AudioContext, crackle: boolean) {
  const t0 = ctx.currentTime + 0.05;
  const master = ctx.createGain();
  master.gain.value = 0.32;
  master.connect(ctx.destination);

  const base = 392; // G4
  const partials: [number, number, number][] = [
    [1, 1, 4.5],
    [2.0, 0.42, 3.2],
    [2.76, 0.3, 2.4],
    [5.4, 0.12, 1.4],
  ];
  for (const [ratio, amp, decay] of partials) {
    const osc = ctx.createOscillator();
    const env = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = base * ratio;
    env.gain.setValueAtTime(0.0001, t0);
    env.gain.exponentialRampToValueAtTime(amp, t0 + 0.012);
    env.gain.exponentialRampToValueAtTime(0.0001, t0 + decay);
    osc.connect(env).connect(master);
    osc.start(t0);
    osc.stop(t0 + decay + 0.1);
  }
  if (!crackle) return;

  const noise = ctx.createBuffer(1, Math.floor(ctx.sampleRate * 0.05), ctx.sampleRate);
  const data = noise.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  let at = t0 + CRACKLE_AT_S;
  for (let i = 0; i < 16; i++) {
    const src = ctx.createBufferSource();
    const band = ctx.createBiquadFilter();
    const env = ctx.createGain();
    src.buffer = noise;
    band.type = "bandpass";
    band.frequency.value = 2500 + Math.random() * 4000;
    band.Q.value = 6;
    const peak = 0.05 + Math.random() * 0.12;
    env.gain.setValueAtTime(0.0001, at);
    env.gain.exponentialRampToValueAtTime(peak, at + 0.004);
    env.gain.exponentialRampToValueAtTime(0.0001, at + 0.04);
    src.connect(band).connect(env).connect(master);
    src.start(at);
    src.stop(at + 0.05);
    at += 0.04 + Math.random() * 0.1;
  }
}

const ANNOUNCE = [
  "",
  "",
  "",
  "1% Club.",
  "1% Club. 1% spark. 99% sweat.",
  "You bring the spark. Scan the code to share your idea.",
];

function on(base: string, shown: boolean) {
  return shown ? `${base} is-on` : base;
}

/** How long an announcement stays in the live region before it is cleared, so the reading order never holds the
 * same words twice (review A3). */
const ANNOUNCE_FOR_MS = 2500;

export function LaunchStage({ url, shownUrl, qr }: Props) {
  const [step, setStep] = useState<number | null>(null);
  const [clearedStep, setClearedStep] = useState<number | null>(null);
  const timers = useRef<number[]>([]);
  const audio = useRef<AudioContext | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const startButton = useRef<HTMLButtonElement>(null);
  const backButton = useRef<HTMLButtonElement>(null);
  const started = step !== null;

  const stop = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
    audio.current?.close().catch(() => undefined);
    audio.current = null;
  }, []);

  useEffect(() => stop, [stop]);

  // The screen covers the page: take the header, banners and footer out of the tab order and the reading order
  // while it is open, so keyboard focus never lands somewhere hidden behind it.
  useEffect(() => {
    const behind = document.querySelectorAll<HTMLElement>(".skip-link, .site-header, .banners, .site-footer");
    behind.forEach((el) => el.setAttribute("inert", ""));
    return () => behind.forEach((el) => el.removeAttribute("inert"));
  }, []);

  useEffect(() => {
    (started ? backButton : startButton).current?.focus();
  }, [started]);

  // Say what just appeared, then clear it: the visible words are in the reading order once they show.
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
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (typeof window.AudioContext === "function") {
      try {
        audio.current = new window.AudioContext();
        playSignature(audio.current, !reduced);
      } catch {
        audio.current = null; // no sound is better than no launch
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

  function back() {
    stop();
    setClearedStep(null);
    setStep(null);
  }

  function fullScreen() {
    root.current?.requestFullscreen?.().catch(() => undefined);
  }

  const s = step ?? -1;
  return (
    <div ref={root} className="launch">
      {!started ? (
        <div className="launch-intro">
          <h1>Launch screen</h1>
          <p>
            For the lamp lighting on Friday 20 November. Put this page on the big screen, choose Full screen,
            then press Start the moment the lamp is lit.
          </p>
          <p>
            It runs for about thirty seconds, with a bell and a spark sound at the start, and then stays on
            the invitation and its QR code.
          </p>
          <div className="launch-controls">
            <button ref={startButton} type="button" className="btn btn-primary btn-lg" onClick={start}>
              Start
            </button>
            <button type="button" className="btn btn-secondary btn-lg launch-ghost" onClick={fullScreen}>
              Full screen
            </button>
          </div>
        </div>
      ) : (
        <div className="launch-stage">
          <div className="launch-hero">
            <svg className="launch-mark" viewBox="0 0 200 240" aria-hidden="true" focusable="false">
              <circle
                className={on("launch-zero", s >= 2)}
                cx="52"
                cy="58"
                r="34"
                fill="none"
                stroke="currentColor"
                strokeWidth="12"
              />
              <circle
                className={on("launch-zero", s >= 2)}
                cx="148"
                cy="184"
                r="34"
                fill="none"
                stroke="currentColor"
                strokeWidth="12"
              />
              <polygon
                className={on("launch-spark", s >= 1)}
                points="34,236 146.9,27.2 169.1,40.8"
                fill={SPARK}
              />
              <circle className={on("launch-ember", s >= 1)} cx="171.6" cy="11.8" r="7" fill={SPARK} />
            </svg>
            {/* Each part stays out of the accessibility tree until its moment (review A3). */}
            <div className="launch-words">
              <h1 className={on("launch-name", s >= 3)} aria-hidden={s < 3 ? true : undefined}>
                1% Club
              </h1>
              <p className={on("launch-tagline", s >= 4)} aria-hidden={s < 4 ? true : undefined}>
                1% spark. 99% sweat.
              </p>
            </div>
          </div>
          <div className={on("launch-invite", s >= 5)} aria-hidden={s < 5 ? true : undefined}>
            <svg
              className="launch-qr"
              viewBox={`-4 -4 ${qr.size + 8} ${qr.size + 8}`}
              role="img"
              aria-label={`QR code for ${url}`}
              shapeRendering="crispEdges"
            >
              <rect x="-4" y="-4" width={qr.size + 8} height={qr.size + 8} fill="#FFFFFF" />
              <path d={qr.d} fill="#0A0A0C" />
            </svg>
            <div>
              <p className="launch-invite-line">You bring the spark.</p>
              <p className="launch-url">{shownUrl}</p>
            </div>
          </div>
          <p className="visually-hidden" aria-live="polite">
            {announcement}
          </p>
          <button ref={backButton} type="button" className="launch-back" onClick={back}>
            Back to start
          </button>
        </div>
      )}
    </div>
  );
}
