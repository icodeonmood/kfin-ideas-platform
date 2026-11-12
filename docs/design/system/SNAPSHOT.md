# Design system snapshot (lane D)

This folder is a copy of the 1% Club design system "molten glass" (DEC-099), artifact
https://claude.ai/artifact/YBh9eYsRUYpSfK98cBJZeF, version `1794413515-4a98`: the version the app's vendored files
were built from (BLD-D001). The artifact is the source of truth. The product lead revises it in place, so this copy
can fall behind; re-copy it when the vendored files are re-synced. It replaces the v1 snapshot (old tier colours,
superseded by DEC-098).

The code lives in the app, not here:

| File | What it is |
|---|---|
| `apps/web/src/app/ds-tokens.css` | `tokens.json` compiled to custom properties |
| `apps/web/src/app/ds.css` | the artifact's `components/bundle.css`, byte for byte, minus its Google Fonts import |
| `apps/web/public/ds/opc.js` | the artifact's `components/bundle.js`, byte for byte (GSAP 3.13, DEC-100) |
| `apps/web/src/app/ds-app.css` | the app's own rules and fixes, loaded last |

## Corrections in this copy (to send back to the artifact)

Three usage notes in `tokens.json` are corrected here to match DEC-098 and the app:

1. `spark`: no longer "a One's number at Tier 1". Tier 1 is `tier-1` (#ff7f14).
2. `tier-6` and `tier-7`: no longer "the jersey number's lower half". Their numbers end on a lighter mix of the colour, because the colour itself is under 3:1 on Graphite (BLD-D007).

The other fixes the app makes on top of the system are listed in `docs/design/SCREENS.md` ("Design-system fixes to send back to the artifact").
