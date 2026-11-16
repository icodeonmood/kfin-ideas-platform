"use client";

/**
 * S-OFFICE (L-DISPLAY.office): the Ones, one at a time. A field of lights, one per One, labelled "No. 1 · Rohit",
 * the current One's brightest; on the left their card (tier, the rolling number, name, flag, brief and headline
 * figure, "1 of 7"). Silent. Rotates every `seconds`; reduced motion still rotates, but the roll, the build and the
 * light changes cut (S-OFFICE/5). Pause stops the rotation and every loop (WCAG 2.2.2). The data refreshes every
 * few minutes without a reload; if a refresh fails, the screen keeps what it has.
 */
import { Fragment, useEffect, useRef, useState, type CSSProperties } from "react";

import {
  countLine,
  digitsOf,
  dustField,
  flagWords,
  lightLabel,
  lightSize,
  placeInSky,
  position,
  sparkShape,
  tierLine,
  type OfficeData,
  type OfficeOne,
  type StarStyle,
} from "@/lib/display";
import { BANNERS } from "@/lib/killswitch-routes";

import { fullScreen, useDisplaySurface } from "../surface";

const REFRESH_MS = 3 * 60_000;
const DUST = dustField();
const NO_COLOUR = "#3355FF";

type Props = { initial: OfficeData | null; seconds: number; stars: StarStyle };

const u = (px: number) => `calc(${px} * var(--u))`;

function Light({
  one,
  current,
  style,
  order,
}: {
  one: OfficeOne;
  current: boolean;
  style: StarStyle;
  order: number;
}) {
  const at = placeInSky(one.induction_no);
  const size = lightSize(style, one.tier, current);
  const spark = sparkShape(one.induction_no);
  return (
    <li
      className="do-light"
      style={{
        left: `${at.x}%`,
        top: `${at.y}%`,
        width: u(size.box),
        height: u(size.box),
        opacity: size.opacity,
        animationDelay: `${order * 0.25}s`,
      }}
    >
      {current ? (
        <span
          className="do-halo"
          aria-hidden="true"
          style={{
            width: u(size.halo),
            height: u(size.halo),
            margin: `${u(-size.halo / 2)} 0 0 ${u(-size.halo / 2)}`,
          }}
        />
      ) : null}
      {style === "dots" ? (
        <span
          className="do-dot"
          aria-hidden="true"
          style={{
            background: one.tier_colour,
            boxShadow: `0 0 ${u(size.dotGlow)} ${one.tier_colour}, 0 0 ${u(4)} #FFFFFF`,
          }}
        />
      ) : (
        <svg
          className="do-spark"
          viewBox="0 0 100 100"
          aria-hidden="true"
          focusable="false"
          style={{ filter: `drop-shadow(0 0 ${u(size.sparkGlow)} ${one.tier_colour})` }}
        >
          <polygon points={spark.points} fill={one.tier_colour} />
          <circle
            cx={spark.ember[0].toFixed(1)}
            cy={spark.ember[1].toFixed(1)}
            r="3.5"
            fill={one.tier_colour}
          />
        </svg>
      )}
      <span className={current ? "do-bub is-on" : "do-bub"}>
        <span className="do-bdot" aria-hidden="true" style={{ background: one.tier_colour }} />
        {lightLabel(one)}
      </span>
    </li>
  );
}

function Words({ text, base }: { text: string; base: number }) {
  return text.split(" ").map((word, j) => (
    <Fragment key={j}>
      <span className="do-wd" style={{ "--base": `${base}ms`, "--j": j } as CSSProperties}>
        {word}
      </span>{" "}
    </Fragment>
  ));
}

export function OfficeScreen({ initial, seconds, stars }: Props) {
  const [data, setData] = useState<OfficeData | null>(initial);
  const [index, setIndex] = useState(0);
  const [run, setRun] = useState(0);
  const [paused, setPaused] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const shownNumber = useRef<number | null>(null);

  useDisplaySurface(root);

  const ones = data?.ones ?? [];
  const count = ones.length;
  const i = count ? index % count : 0;
  const current = count ? ones[i] : undefined;
  const currentNumber = current?.number ?? null;
  useEffect(() => {
    shownNumber.current = currentNumber;
  }, [currentNumber]);

  // The rotation: one One at a time. It keeps going with reduced motion; only Pause stops it.
  useEffect(() => {
    if (paused || count < 2) return;
    const t = window.setInterval(() => {
      setIndex((x) => (x + 1) % count);
      setRun((r) => r + 1);
    }, seconds * 1000);
    return () => window.clearInterval(t);
  }, [paused, count, seconds]);

  // Fresh data every few minutes, without reloading; the One on screen stays on screen if it is still there.
  useEffect(() => {
    let live = true;
    const t = window.setInterval(async () => {
      try {
        const res = await fetch("/api/display/office", { cache: "no-store" });
        if (res.status === 503) {
          // `ones.public` switched off: the Ones leave the screen and it shows the resting line.
          const body = (await res.json().catch(() => ({}))) as { switch?: string };
          if (live && body.switch === "ones.public") setData({ paused: true, ones: [] });
          return;
        }
        if (!res.ok) return; // signed out, or the network: keep what is on screen
        const next = (await res.json()) as OfficeData;
        if (!live) return;
        const at = next.ones.findIndex((o) => o.number === shownNumber.current);
        setData(next);
        setIndex(at >= 0 ? at : 0);
      } catch {
        // the network dropped: try again at the next refresh
      }
    }, REFRESH_MS);
    return () => {
      live = false;
      window.clearInterval(t);
    };
  }, []);

  const colour = current?.tier_colour ?? NO_COLOUR;
  const odd = run % 2 === 1;
  const words = current ? [current.brief, current.figure].filter(Boolean).join(" ") : "";
  return (
    <div ref={root} className="dsp do" tabIndex={-1}>
      <div
        className={paused ? "dsp-stage do-stage is-paused" : "dsp-stage do-stage"}
        role="region"
        aria-label="The Ones, in the sky"
        style={
          {
            "--do-colour": colour,
            "--do-glow-soft": `${colour}1F`,
            "--do-glow-a": `${colour}5C`,
            "--do-glow-b": `${colour}00`,
            "--dwell": `${seconds}s`,
          } as CSSProperties
        }
      >
        <div className="do-sky" aria-hidden="true" />
        <div className="do-dust" aria-hidden="true">
          {DUST.map((d, k) => (
            <span
              key={k}
              className="do-star"
              style={
                {
                  left: `${d.x}%`,
                  top: `${d.y}%`,
                  width: u(d.size),
                  height: u(d.size),
                  background: `rgba(255,255,255,${d.alpha})`,
                  "--d": d.delay,
                } as CSSProperties
              }
            />
          ))}
        </div>
        {count ? (
          <ul className="do-lights" aria-label="The Ones">
            {ones.map((one, k) => (
              <Light key={one.number} one={one} current={k === i} style={stars} order={k} />
            ))}
          </ul>
        ) : null}

        <div className="do-head">
          <div>
            <p className="do-eyebrow">1% Club · KFintech</p>
            <h1 className="do-title">The Ones</h1>
            {data?.paused ? (
              <p className="do-count">{BANNERS["ones.public"]}</p>
            ) : count ? (
              <p className="do-count">{countLine(count)}</p>
            ) : null}
          </div>
          <div className="do-controls">
            <button
              type="button"
              className="do-round"
              aria-label={paused ? "Play the screen" : "Pause the screen"}
              onClick={() => setPaused((p) => !p)}
            >
              <svg width="22" height="22" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
                <path d={paused ? "M7 5v10l8-5z" : "M7.5 5v10M12.5 5v10"} />
              </svg>
            </button>
            <button
              type="button"
              className="do-round"
              aria-label="Full screen"
              onClick={() => fullScreen(root.current)}
            >
              <svg width="22" height="22" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
                <path d="M4 8V4h4M12 4h4v4M16 12v4h-4M8 16H4v-4" />
              </svg>
            </button>
          </div>
        </div>

        {current ? (
          <article className={odd ? "do-card is-b" : "do-card is-a"} aria-live="off">
            <div className="do-fill" aria-hidden="true" />
            <div className="do-card-in">
              <div className="do-tier">
                <span className="do-fill do-bar" aria-hidden="true" />
                <p>
                  <span className="do-wd" style={{ "--base": "300ms" } as CSSProperties}>
                    {tierLine(current)}
                  </span>
                </p>
              </div>
              <div className="do-who">
                <p className="do-number">
                  <span className="dsp-vh">Number {current.number}</span>
                  <span aria-hidden="true">
                    {digitsOf(current.number).map((d, k) => (
                      <span key={k} className="do-dg">
                        <span className="do-col" style={{ transform: `translateY(-${d}em)` }}>
                          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
                            <span key={n}>{n}</span>
                          ))}
                        </span>
                      </span>
                    ))}
                  </span>
                </p>
                <div className="do-name-block">
                  {current.name ? (
                    <p className="do-name">
                      <span className="do-wd" style={{ "--base": "500ms" } as CSSProperties}>
                        {current.name}
                      </span>
                    </p>
                  ) : null}
                  <p className="do-flag">
                    <span className="do-wd" style={{ "--base": "650ms" } as CSSProperties}>
                      {flagWords(current.flag)}
                    </span>
                  </p>
                </div>
              </div>
              {words ? (
                <p className="do-brief">
                  <Words text={words} base={800} />
                </p>
              ) : null}
              <div className="do-progress">
                <span className="do-pos">{position(i, count)}</span>
                <span className="do-track" aria-hidden="true">
                  <span className={odd ? "do-run is-b" : "do-run is-a"} />
                </span>
              </div>
            </div>
          </article>
        ) : null}

        <p className="do-tagline">1% spark. 99% sweat.</p>
      </div>
    </div>
  );
}
