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
      <div className="sky" ref={root}>
        <div className="sky-words">
          <h1>The Ones are resting for now.</h1>
        </div>
      </div>
    );
  }

  const glowing = ambient ? active[glow % Math.max(1, active.length)] : undefined;
  const glowCard = glowing ? cards.find((c) => c.induction_no === glowing.induction_no) : undefined;
  const shown = card >= 0 ? cards[card] : undefined;
  return (
    <div className="sky" ref={root} aria-label="The Ones, in the sky">
      <div className="sky-controls">
        <button
          type="button"
          className="round-button"
          aria-label={paused ? "Play the screen" : "Pause the screen"}
          onClick={() => setPaused((p) => !p)}
        >
          {paused ? "▶" : "❚❚"}
        </button>
        <button
          type="button"
          className="round-button"
          aria-label="Full screen"
          onClick={() => root.current?.requestFullscreen?.().catch(() => undefined)}
        >
          ⤢
        </button>
      </div>

      {shown ? (
        <div className="sky-card">
          <p className="one-number" style={{ color: shown.tier_colour }}>
            <span className="visually-hidden">Number </span>
            {shown.number}
          </p>
          <div style={{ display: "grid", gap: "1rem" }}>
            <h2>{oneName(shown.number, shown.name)}</h2>
            {shown.line ? <p className="one-line">{shown.line}</p> : null}
            <p className="one-brief">{shown.brief}</p>
            <p className="one-tier">
              <span className="tier-dot" style={{ background: shown.tier_colour }} aria-hidden="true" />
              Tier {shown.tier}, {shown.tier_name}. {oneTag(shown)}
            </p>
            <ul className="measure-chips">
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
                  color: s.tier_colour,
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
            <p style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.625rem" }}>
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
