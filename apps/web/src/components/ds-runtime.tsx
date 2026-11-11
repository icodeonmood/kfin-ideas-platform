"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

/**
 * Loads the design system's behaviour script (public/ds/opc.js: GSAP 3.13, DEC-100, plus the system's own wiring)
 * after the page is interactive, and re-runs its idempotent `init` whenever a route renders or React adds markup,
 * so liquid buttons, the nav thumb, rim light and refraction reach content that arrives later (DEC-099).
 *
 * Everything the script adds is decorative, `aria-hidden` and unfocusable; without it every control still works.
 * It honours prefers-reduced-motion by itself.
 */
type OnePercentClub = { init?: (root: Element) => void };

function runInit() {
  const opc = (window as unknown as { OnePercentClub?: OnePercentClub }).OnePercentClub;
  opc?.init?.(document.body);
}

export function DsRuntime() {
  const pathname = usePathname();

  useEffect(() => {
    runInit();
    const main = document.getElementById("main");
    if (!main) return;
    let timer: number | undefined;
    // React adds markup after the first paint (scan results, match cards, a confirmation). `init` skips what it
    // has already wired, so a short debounce is enough to catch the rest without work on every keystroke.
    const observer = new MutationObserver((records) => {
      if (!records.some((r) => r.addedNodes.length > 0)) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(runInit, 80);
    });
    observer.observe(main, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      window.clearTimeout(timer);
    };
  }, [pathname]);

  return <Script src="/ds/opc.js" strategy="afterInteractive" onLoad={runInit} />;
}
