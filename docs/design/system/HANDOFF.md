# Hand-off

How this system reaches the app once the product lead approves it. Nothing below is built yet.

## Where it goes

| This system | The app (`kfin-ideas-platform`) |
|---|---|
| `tokens.json` → `tokens.css` | The `:root` and `[data-theme]` blocks at the top of `apps/web/src/app/globals.css`. Brand values unchanged; semantic names added |
| `components/bundle.css` | Replaces the matching ad-hoc rules in `globals.css`, class by class. Still one plain CSS file, no Tailwind, no component library |
| Glyphs | One `apps/web/src/components/glyph.tsx` with the dozen inline SVGs |
| Status, ConfirmInPlace, SectionNav | Three small shared components in `apps/web/src/components/` |
| Branded loading, error and not-found | `app/loading.tsx`, `app/error.tsx`, `app/not-found.tsx` (if approved) |

## What must not change

The e2e suite finds things by role, label, heading, button name and status text. Every accessible name, on-screen word, element id (`#f-…` field ids, error-summary anchors), role and live region, with its announcement cadence, stays exactly as it is, unless the product lead approves new copy, in which case the tests change in the same commit. Kill-switch checks, "Coming soon" banners and role checks are untouched. Match cards still show only the neutral summary, area tag, stage and count.

## Order

P0 first (the inauguration path), merged to `main` with lint, unit, e2e and axe green by Mon 16 Nov. P1 and P2 continue on the branch after launch, with the lead's OK for each merge. Lane C finishes behaviour on the canvas, Find your crew and the voice note first; lane D then changes CSS and markup only.

## Two traps found while checking this system (11 Nov)

1. **axe and entrance motion.** axe measured contrast on match cards while they were still fading in and reported a failure that disappears once they settle. Run the e2e suite with Playwright's `reducedMotion: "reduce"` (the system then shows end states at once), or let axe wait for animations to finish, so the checks never flake.
2. **Grid children and wide content.** A grid child defaults to its min-content width, so a file input or a long word widens the whole page at 360 px (today's canvas bug). The system sets `min-width: 0` on field, file and voice children; keep that when porting.
