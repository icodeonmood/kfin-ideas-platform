# Hand-off

How this system reaches the app once the product lead approves it. Nothing below is built in the app yet.

## Where it goes

| This system | The app (`kfin-ideas-platform`) |
|---|---|
| `tokens.json` → `tokens.css` | The `:root` and `[data-theme]` blocks at the top of `apps/web/src/app/globals.css`. Brand values unchanged; the glass, heat, shadow, blur and spring tokens are new |
| `components/bundle.css` | Replaces the matching ad-hoc rules in `globals.css`, class by class. Still one plain CSS file, no Tailwind, no component library |
| `components/bundle.js` | New. One script, loaded once in the root layout after the page's own markup is ready. It carries GSAP 3.13 and exposes `window.OnePercentClub`. In React, call `OnePercentClub.init(node)` from a layout effect after a route renders new markup |
| `class="stage"` and `data-tier` | On `<body>` in the root layout: `data-theme` as today, `data-tier` from the signed-in user's tier (0 when not a One). The page ground becomes the matte grey (`matte`), not pure white; brand to confirm, since BRAND.md names White as the working page |
| Glyphs | One `apps/web/src/components/glyph.tsx` with the inline SVGs |
| Status, ConfirmInPlace, SectionNav | Three small shared components in `apps/web/src/components/` |
| Branded loading, error and not-found | `app/loading.tsx`, `app/error.tsx`, `app/not-found.tsx` (if approved) |

## What is new to approve

| Item | Why it needs a yes |
|---|---|
| GSAP as a dependency (about 72 KB, inside `bundle.js`) | A new runtime dependency under a licence that is free for commercial use but not open source. Legal to confirm. Fallback: the Web Animations API |
| The floating dock in place of the square Zed header | Pages now reserve 80 px at the top and scroll under the dock |
| New copy | "Menu", "Try again", "Remove it", "Keep it", "No personal details found. Keep writing.", "Drop files here, or browse", "Each file is checked before anyone can open it.", "Move it on" is preview-only. All to HR (DEC-091) |
| Spark tiers on screen | See the Spark tiers section, open points 1 to 4 |

## What must not change

The e2e suite finds things by role, label, heading, button name and status text. Every accessible name, on-screen word, element id (`#f-…` field ids, error-summary anchors), role and live region, with its announcement cadence, stays exactly as it is, unless the product lead approves new copy, in which case the tests change in the same commit. Kill-switch checks, "Coming soon" banners and role checks are untouched. Match cards still show only the neutral summary, area tag, stage and count. Everything `bundle.js` adds to the page (liquid layers, thumbs, the light canvas, filter definitions) is `aria-hidden` and takes no focus.

## Order

P0 first (the inauguration path), merged to `main` with lint, unit, e2e and axe green by Mon 16 Nov. That date was set for the first proposal; this edition is larger, so the product lead should decide whether P0 ships on the first proposal's CSS with this edition following, or waits. P1 and P2 continue on the branch after launch, with the lead's OK for each merge. Lane C finishes behaviour on the canvas, Find your crew and the voice note first; lane D then changes CSS and markup only.

## Traps

1. **axe and motion.** axe measured contrast on match cards while they were still arriving and reported a failure that disappears once they settle. Run the e2e suite with Playwright's `reducedMotion: "reduce"` (the system then shows end states at once), so the checks never flake.
2. **Grid children and wide content.** A grid child defaults to its min-content width, so a file input or a long word widens the whole page at 360 px (today's canvas bug). The system sets `min-width: 0` on field, file and voice children; keep that when porting.
3. **A class called `pd`.** The personal-data marks are `mark.pd`. Don't give a layout wrapper the same class: it turned the marks into grid containers while this edition was being built. The wrapper is `pd-check`.
4. **Refraction is Chromium-only.** Safari and Firefox show the glass with blur, rim light and motion but no bend or colour split. That includes every iPhone. Check both; nothing should depend on the bend to be understood. Each lens costs one SVG filter with three displacement passes over its own area: keep lenses small (controls, the bar, the thumb) and give big panes `data-refract` only when they float over content.
5. **Blur is not free.** On the budget Android, test the canvas with no drifting light (working screens have none anyway) and no more than a dozen glass surfaces in view.
6. **`data-theme` re-declares `--heat`.** The tier rules are written as `[data-tier="2"], [data-tier="2"] [data-theme]` so a nested theme does not reset the tier. Keep that pair when porting.
