"use client";

/**
 * The constellation screen. A static sky by default; ambient mode (switched on by an admin for events) makes one
 * spark glow every ten seconds with its number and name beneath. In both modes the sky alternates with
 * full-screen impact cards (DEC-074). Silent. Reduced motion keeps the sky still. Pause stops everything.
 */
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { oneTag } from "@/components/one-card";
import { OneSpark } from "@/components/one-spark";
import { SparkMark } from "@/components/spark-mark";
import { BANNERS } from "@/lib/killswitch-routes";
import { measureList, oneName } from "@/lib/measures";
import { sparkFor } from "@/lib/spark";
import type { constellation } from "@/server/ones";

type Data = Awaited<ReturnType<typeof constellation>> | null;

const SKY_MS = 45_000;
const CARD_MS = 15_000;
const GLOW_MS = 10_000;
const REFRESH_MS = 5 * 60_000;

export function Sky({ data }: { data: Data }) {
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  const [card, setCard] = useState(-1); // -1 is the sky
  const [glow, setGlow] = useState(0);
  const [reduced, setReduced] = useState(false);
  const cards = data?.cards ?? [];
  const sparks = data?.sparks ?? [];
  const active = sparks.filter((s) => s.active);
  const ambient = data?.mode === "ambient" && !reduced;

  useEffect(() => {
    const behind = document.querySelectorAll<HTMLElement>(".skip-link, .site-header, .banners, .site-footer");
    behind.forEach((el) => el.setAttribute("inert", ""));
    const m = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(m.matches);
    const t0 = window.setTimeout(sync, 0);
    m.addEventListener("change", sync);
    const refresh = window.setInterval(() => router.refresh(), REFRESH_MS);
    return () => {
      behind.forEach((el) => el.removeAttribute("inert"));
      window.clearTimeout(t0);
      m.removeEventListener("change", sync);
      window.clearInterval(refresh);
    };
  }, [router]);

  useEffect(() => {
    if (paused || !cards.length) return;
    const t = window.setTimeout(
      () => setCard((c) => (c + 1 >= cards.length ? -1 : c + 1)),
      card < 0 ? SKY_MS : CARD_MS,
    );
    return () => window.clearTimeout(t);
  }, [card, paused, cards.length]);

  useEffect(() => {
    if (paused || !ambient || card >= 0 || active.length < 1) return;
    const t = window.setInterval(() => setGlow((g) => (g + 1) % active.length), GLOW_MS);
    return () => window.clearInterval(t);
  }, [paused, ambient, card, active.length]);

  if (!data || data.paused) {
    return (
      <div className="sky stage" data-theme="zed" ref={root}>
        <div className="sky-words">
          <h1>{BANNERS["ones.public"]}</h1>
        </div>
      </div>
    );
  }

  const glowing = ambient ? active[glow % Math.max(1, active.length)] : undefined;
  const glowCard = glowing ? cards.find((c) => c.induction_no === glowing.induction_no) : undefined;
  const shown = card >= 0 ? cards[card] : undefined;
  return (
    <div
      className="sky stage"
      data-theme="zed"
      data-glow="1"
      ref={root}
      role="region"
      aria-label="The Ones, in the sky"
    >
      <div className="sky-controls">
        <button
          type="button"
          className="round-btn"
          aria-label={paused ? "Play the screen" : "Pause the screen"}
          onClick={() => setPaused((p) => !p)}
        >
          <svg
            className={paused ? "glyph glyph-fill" : "glyph"}
            viewBox="0 0 20 20"
            aria-hidden="true"
            focusable="false"
          >
            <path d={paused ? "M7 5v10l8-5z" : "M7.5 5v10M12.5 5v10"} />
          </svg>
        </button>
        <button
          type="button"
          className="round-btn"
          aria-label="Full screen"
          onClick={() => root.current?.requestFullscreen?.().catch(() => undefined)}
        >
          <svg className="glyph" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
            <path d="M4 8V4h4M12 4h4v4M16 12v4h-4M8 16H4v-4" />
          </svg>
        </button>
      </div>

      {shown ? (
        <div className="sky-card" data-tier={String(Math.min(7, Math.max(1, shown.tier)))}>
          <p className="jersey-num sky-card-num">
            <span className="visually-hidden">Number </span>
            {shown.number}
          </p>
          <div className="sky-card-copy">
            <h2>{oneName(shown.number, shown.name)}</h2>
            {shown.line ? <p className="one-line">{shown.line}</p> : null}
            <p className="one-brief">{shown.brief}</p>
            <p className="one-tier">
              <span className="swatch" aria-hidden="true" />
              Tier {shown.tier}, {shown.tier_name}. {oneTag(shown)}
            </p>
            <ul className="jersey-measures">
              {measureList(shown.measures).map(([label, words]) => (
                <li key={label}>
                  <span>{label}:</span> {words}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <>
          {sparks.map((s) => {
            const p = sparkFor(s.induction_no);
            const isGlowing = glowing?.induction_no === s.induction_no;
            return (
              <div
                key={s.induction_no}
                className={`sky-spark${isGlowing ? " is-glowing" : ""}`}
                style={{
                  left: `${p.x * 100}%`,
                  top: `${p.y * 100}%`,
                  opacity: s.active ? 1 : 0.4,
                  ["--spark-glow" as string]: s.tier_colour,
                }}
              >
                <OneSpark inductionNo={s.induction_no} colour={s.tier_colour} size={isGlowing ? 96 : 64} />
              </div>
            );
          })}
          {glowing ? (
            <p
              className="sky-glow-label"
              style={{
                left: `${sparkFor(glowing.induction_no).x * 100}%`,
                top: `calc(${sparkFor(glowing.induction_no).y * 100}% + 6.5rem)`,
              }}
            >
              {glowCard ? `No. ${glowCard.number}${glowCard.name ? `, ${glowCard.name}` : ""}` : ""}
            </p>
          ) : null}
          <div className="sky-words">
            <div>
              <h1>The Ones</h1>
              <p className="lead-dark">
                Every spark is a One: {active.length} {active.length === 1 ? "colleague" : "colleagues"}{" "}
                building what they noticed.
              </p>
            </div>
            <p className="sky-lockup">
              <SparkMark height={28} />
              <span>
                <strong>1% Club</strong>
                <br />
                <span className="lead-dark">1% spark. 99% sweat.</span>
              </span>
            </p>
          </div>
        </>
      )}
    </div>
  );
}
