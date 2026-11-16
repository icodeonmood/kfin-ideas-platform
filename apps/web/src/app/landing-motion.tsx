"use client";

import { useEffect, useRef } from "react";

const still = () =>
  typeof window === "undefined" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * S-01.rules/4 and F-MOTION.arrive/5: sections marked `data-reveal` rise in once as they enter the viewport. Plain
 * IntersectionObserver and CSS, no animation library (BLD-E005). Without scripts, or with reduced motion, nothing
 * is ever hidden: only this code marks a section "pending", and only below the fold.
 */
export function LandingMotion() {
  useEffect(() => {
    if (still() || !("IntersectionObserver" in window)) return;
    const sections = [...document.querySelectorAll<HTMLElement>(".ld [data-reveal]")];
    const below = sections.filter((el) => el.getBoundingClientRect().top > window.innerHeight);
    below.forEach((el) => (el.dataset.reveal = "pending"));
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          (e.target as HTMLElement).dataset.reveal = "in";
          io.unobserve(e.target);
        }
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    below.forEach((el) => io.observe(el));
    return () => {
      io.disconnect();
      below.forEach((el) => (el.dataset.reveal = ""));
    };
  }, []);
  return null;
}

/** The mark drawn large, tilting a little toward the pointer (S-01.layout/3). Still with reduced motion. */
export function TiltMark() {
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || still() || !window.matchMedia("(pointer: fine)").matches) return;
    let frame = 0;
    const onMove = (e: PointerEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const x = (e.clientX - (r.left + r.width / 2)) / window.innerWidth;
        const y = (e.clientY - (r.top + r.height / 2)) / window.innerHeight;
        el.style.transform = `perspective(900px) rotateY(${(x * 10).toFixed(2)}deg) rotateX(${(-y * 10).toFixed(2)}deg)`;
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onMove);
    };
  }, []);
  return (
    <svg
      ref={ref}
      className="ld-mark"
      viewBox="0 0 200 240"
      role="img"
      aria-label="The 1% mark: two circles joined by a spark"
    >
      <circle cx="52" cy="58" r="34" fill="none" stroke="currentColor" strokeWidth="10" />
      <circle cx="148" cy="184" r="34" fill="none" stroke="currentColor" strokeWidth="10" />
      <polygon className="ld-sp" points="34,236 146.9,27.2 169.1,40.8" fill="#F46835" />
      <circle className="ld-sd" cx="171.6" cy="11.8" r="7" fill="#F46835" />
    </svg>
  );
}
