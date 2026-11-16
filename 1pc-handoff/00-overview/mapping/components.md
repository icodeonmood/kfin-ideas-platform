# 1% Club handoff: foundations, tokens and components mapped onto the repo

Scope: `1pc-handoff/01-foundations/*` and every `02-components/C-*` except `C-SIDEBAR`, `C-PHONE-TABS`, `C-TASKBAR`.
Repo read: worktree `/Users/mantri/rome/kfin-ideas-platform/.worktrees/handoff` at latest `main` (Mon 16 Nov 2026). Read-only; nothing was changed.

Repo files that matter here:

| File | Lines | What it is now |
|---|---|---|
| `apps/web/src/app/offer.css` | 1036 | DEC-101 / BLD-D009 OFFER foundation: tokens (under old names), base, type, `.btn*`, cards, `.status`, fields, `.choice`/`.check`, strength `.slash`, `.jersey`, `.hdr*` header |
| `apps/web/src/app/ds-app.css` | 1935 | Screen layouts in OFFER (home, entry, canvas, scan, crew, my ideas, One dashboard, glow-up, wall, idea page, office/launch) |
| `apps/web/src/app/globals.css` | 1565 | Pre-OFFER DEC-028 sheet: Geist/Electric/Zed `:root`, `.button`, `.notice`, `.panel`, `.table`, old Ones/launch/office/Ember/journey rules. Loaded first; offer.css overrides its tokens |
| `apps/web/src/app/layout.tsx` | 73 | Imports `@fontsource-variable/inter`, `@fontsource-variable/inter-tight`, then globals → offer → ds-app. Top header lockup + `MainNav`, footer |
| `apps/web/src/components/*` | 559 total | `status.tsx`, `idea-card.tsx`, `one-card.tsx` (jersey), `ones-carousel.tsx`, `spark-mark.tsx`, `one-spark.tsx`, `nav.tsx`, `banners.tsx`, `showcase-view.tsx`, `print-button.tsx` |
| Screen-local UI | | `app/share/[id]/canvas-form.tsx` (872), `voice-recorder.tsx` (296), `attachments.tsx` (234), `app/share/[id]/done/crew.tsx` (439), `scan-status.tsx` (392), `app/inbox/message-list.tsx`, `app/my-ideas/glow-up.tsx` (native `<dialog>`) |

Headline: the OFFER neutral base already matches the pack almost hex for hex (the pack's `kit.css` says "same OFFER values as v38, now named"). What differs is the accent layer (blue, spark, warn/bad dots, tiers all "conditioned to 87% chroma"), the shape scale (12/20/28 radii vs 10/20/24), the glass and ambient light that DEC-101 removed, the motion system, and the type scale. About two thirds of the components do not exist as components at all; most screen UI is inline in page files.

---

## 1. Token mapping

### 1.1 Colour (`tokens.json` → `color`)

"Same" = identical value, only the name differs. Action: **keep** (same name and value), **alias** (rename to pack name; keep old name pointing at it during migration), **retune** (value changes), **add** (no repo token).

| Pack token | Pack value | Repo token (offer.css) | Repo value | Action |
|---|---|---|---|---|
| `--ink` | `#111111` | `--ink` | `#111111` | keep |
| `--ink2` | `#2A2A2E` | none (raw `#2a2a2e` in `.btn-primary:hover`) | | add |
| `--mute2` | `#4A4A50` | none | | add (body text, sort options, tabs at rest) |
| `--mute` | `#5F5F64` | `--ink-muted` (also `--muted`, `--slate`) | `#5f5f64` | alias |
| `--faint` | `#6C6C70` | none | | add (neutral pill dot, chevrons) |
| `--paper` | `#F3F3F1` | `--paper` (`--bg`) | `#f3f3f1` | keep |
| `--card` | `#FFFFFF` | `--card` (`--surface`, `--g-fill`, `--g-well`) | `#ffffff` | keep |
| `--cardGlass` | `rgba(255,255,255,.78)` | none (DEC-101 removed glass) | | add |
| `--sunk` | `#E9E9E6` | `--sunken` | `#e9e9e6` | alias |
| `--rule` | `#DADAD6` | `--rule` | `#dadad6` | keep |
| `--rule2` | `#E4E4E0` | `--line` (`--border`, `--line-light`) | `#e4e4e0` | alias |
| `--edge` | `#D0D0CB` | `--line-control` | `#d0d0cb` | alias; **stop using it for field borders** (see 3.2) |
| `--blue` | `#395DED` | `--blue` (`--accent`, `--electric`, `--focus`) | `#3355ff` | retune |
| `--blueT` | `#2948C6` | none (raw `#2340d8` on checked `.choice`) | | add |
| `--wash` | `#EEF1FF` | `--blue-wash` | `#eef2ff` | alias + retune (1 step) |
| `--spark` | `#F46835` | `--spark`; also `SPARK = "#FF5B14"` hard-coded in `components/spark-mark.tsx` | `#ff5b14` | retune (CSS, SparkMark constant, email PNG marks from BLD-A170, `docs/BRAND.md`) |
| `--okD` / `--okT` / `--okW` | `#12B76A` / `#067647` / `#ECFDF3` | `--ok-dot` / `--ok` / `--ok-wash` | same | alias |
| `--warnD` | `#EE953A` | `--warn-dot` | `#f79009` | alias + retune |
| `--warnT` / `--warnW` | `#B54708` / `#FFFAEB` | `--warn-ink` / `--warn-wash` | same | alias |
| `--badD` | `#E55446` | `--error-dot` | `#f04438` | alias + retune |
| `--badT` / `--badW` | `#B42318` / `#FEF3F2` | `--error` / `--error-wash` | same | alias |
| (none) | | `--error-line` `#fecdca`, `#fedf89` raw (status borders) | | delete: pack uses an inset ring `rgba(180,35,24,.14)` / `rgba(181,71,8,.16)` |
| `--fieldBorder` | `#8C8C91` | none; fields use `--line-control` `#d0d0cb` | | add, and switch every field to it |
| `--placeholder` | `#6B6B70` | placeholders use `--ink-muted` `#5f5f64` | | add |
| `--underline` | `#A3A3A6` | `--ash` is the same hex but means "secondary text on dark" | | add as its own token |
| `--underlineBlue` | `#B9C3FF` | none | | add |
| `--noteBlueText` | `#1E2E99` | none | | add |
| `--softHover` | `#E0E0DC` | none | | add |
| `--avatar` / `--avatarInRing` / `--ringNeutral` | `#E2E2DE` / `#ECECE8` / `#D9D9DE` | none (no avatars in repo) | | add |
| `--skeletonHi` | `#F1F1EE` | none | | add |
| `--slab` | `#18191D` | `.jersey` raw `#16161a`; `--graphite` `#1a1a1e`; zed bg `#111111` | | add; retune jersey and dark panel fills to it |
| (focus glow) | `rgba(57,93,237,.16)` | `--field-glow` `rgba(51,85,255,.16)` | | retune (follows blue) |
| (none) | | `--line-soft` `#ededea` | | no pack role; fold into `--rule2` |

Tiers (`tokens.json` → `tier`):

| Tier | Pack key | Repo `--tier-N` (DEC-098) | Pack ring | Action |
|---|---|---|---|---|
| 1 Spark | `#F5863B` | `#ff7f14` | conic 5-stop | retune + add `--tier-N-ring` |
| 2 Glow | `#F35532` | `#ff4313` | ″ | ″ |
| 3 Flame | `#F34770` | `#ff2e6b` | ″ | ″ |
| 4 Blaze | `#F23729` | `#ff0000` | ″ | ″ |
| 5 White heat | `#4DD187` | `#27d57f` | ″ | ″ |
| 6 Blue flame | `#8841E1` | `#8c2ff1` | ″ | ″ (`OPEN:` name/colour pairing, `F-COLOR.tiers`) |
| 7 Star | `#264DC9` | `#1e46d9` | ″ | ″ |

Tier colours live in four places, all of which must move together: `offer.css`, `services/worker/ones/tiers.py` (feeds `tier_colour` to the app and the emails), `docs/BRAND.md`, and the DEC-098 row. The unit test `apps/web/tests/unit/tier-colour-text.test.ts` (tier colour never as text) stays valid under the pack: tiers are rings, bars and glows.

### 1.2 Type (`tokens.json` → `font`, `type`)

| Pack | Pack value | Repo | Repo value | Action |
|---|---|---|---|---|
| `--fd` | `'Inter Tight',Inter,'Inter Fallback',system-ui,sans-serif` | `--font-display` | `"Inter Tight Variable","Inter Tight","Inter Variable",Inter,system-ui,sans-serif` | alias; override `--fd` to lead with `"Inter Tight Variable"` (see 1.7) |
| `--ft` | `Inter,'Inter Fallback',system-ui,sans-serif` | `--font-sans` (`--font`) | `"Inter Variable",Inter,system-ui,…,Arial` | alias; override `--ft` to lead with `"Inter Variable"` |
| `'Inter Fallback'` face | local Arial, size-adjust 107%, ascent 90%, descent 22.5%, line-gap 0 | none | | add (no download, stops the swap jump) |
| base settings | `cv11`, antialiased, kerning normal, optimizeLegibility, **letter-spacing −0.006em** | `cv11`, antialiased, optimizeLegibility | | add letter-spacing and `font-kerning` |
| text-wrap | balance on h1–h3, legend; **pretty** on p, li, dd, dt, summary, figcaption | balance on `.t-display` and one idea title only | | add |
| `d1` | `500 clamp(44px,4.6vw,64px)/1.02`, −0.035em | `.t-display` | `500 clamp(45px,5.84vw,90px)/1.02`, −0.028em | retune (pack is smaller: max 64 vs 90) |
| `d2` | `500 clamp(35px,4vw,58px)/1.06`, −0.028em | none | | add (Wall section heads) |
| `h1` | `500 40px/1.08`, −0.03em | `.t-h1` | `clamp(32px,3.4vw,48px)/1.06`, −0.028em | retune; screens mostly use `.t-display` as page title today, pack wants `h1` 40px |
| `h2` | `500 28px/1.12`, −0.024em (24 in sheets) | `.t-h2` | `clamp(22px,2vw,26px)/1.15`, −0.02em | retune |
| `h3` | `500 19px/1.3`, −0.014em | no class; `.idea-title` 20/1.25 −0.015em; `.crew-card > h4` 24px | | add `.h3`; retune titles |
| `lead` | `400 18px/1.55`, `--mute`, max 62ch | `.lead` 19px/1.55 muted (globals caps 40rem) | | retune |
| `body` | `400 15.5px/1.6`, `--mute2`, max 65ch | body 16px/1.5 ink; `--measure: 68ch` | | retune |
| `label` | `500 15px/1.4` | globals `label {font-weight:600}`; canvas labels vary | | retune |
| `meta` | `400 13.5px/1.45`, +0.004em | none (13.5–14px ad hoc) | | add |
| `pill` | `500 13px/1.4` | none | | add |
| `micro` | 12–12.5px, 500–600 | `.eyebrow` 11px caps +0.12em (unused in TSX) | | add `micro`; delete `.eyebrow` (`F-TYPE.rules/1`) |
| big figures | display 500, −0.04em, lh .95, tnum; One's number 80px | `.jersey-num` 88px lh .9 −0.04em tnum; `.jersey-lg` clamp(120,14vw,168); `.glow-num` clamp(96,16vw,152) | | retune to 80px (Wall/One); glow-up per `S-ONE` |
| phone overrides | base 15, d1 32, h1 28, h2 21, h3 17, lead 16, meta 13 | none (fluid clamps instead) | | add under `@media (max-width:640px)` |

### 1.3 Space and layout (`tokens.json` → `space`, `breakpoint`)

| Pack | Value | Repo | Value | Action |
|---|---|---|---|---|
| scale | 4, 8, 12, 16, **20**, 24, 32, **40**, 48, **56**, 72, **104** | `--space-1…9` | 4, 8, 12, 16, 24, 32, 48, 72, **120** | add the missing steps. **Do not renumber** `--space-N` (pack's 5th step is 20, repo's `--space-5` is 24); add px-named tokens (`--sp-20`, `--sp-40`, `--sp-56`, `--sp-104`) and alias the old ones |
| page gutter | 48 desktop / 20 phone | `--gutter` | `clamp(20px,3.4vw,48px)` | retune to fixed per breakpoint |
| content max | 1280 | `--page-max` | 1344 | retune |
| sidebar / folded | 256 / 76 | none (top header) | | add (owned by the C-SIDEBAR agent) |
| target min / control heights | 44 / 48 / 44 small / 56 full | buttons 48 (`.btn-lg` 52, `.btn-sm` 40), fields 48 (canvas 52), choices 48 | | retune: full buttons 56, small 44, chips 40 desktop / 44 phone |
| breakpoints | phone ≤640, tablet ≤1100, design 1440 / 390 | `40rem` (=640) ✓, plus ad hoc 48, 56, 60, 64rem | | keep 640; add 1100; retire the ad hoc ones as screens are rebuilt |
| `scroll-margin-block` | `96px 140px` on everything (16/120 in phone scroll area) | none | | add (needed once sticky bars exist) |
| `scrollbar-gutter` | stable | none | | add |

### 1.4 Radius (`tokens.json` → `radius`)

| Pack | Value | Repo | Value | Action |
|---|---|---|---|---|
| `--r-xs` | 8 | none (raw 8px ×3) | | add |
| `--r-sm` | 12 | `--radius` / `--r-well` | **10** (buttons, fields, header buttons) | retune 10 → 12 |
| `--r-md` | 20 | `--r-card` | 20 | alias |
| `--r-lg` | 28 | `--r-glass` | **24** (glow-up); jersey 16 | retune to 28 (sheets, pop-ups, Home prompt, crew and Ones cards) |
| `--r-pill` | 999 | `--radius-pill` | 999 | alias |
| `--r-round` | 50% | raw 50% | | add |
| hairlines | 2–3px only for the sidebar bar and tier bar | raw 2, 3, 4, 6, 14, 16px, 1rem, 1.25rem in CSS | | `V-ACC.visual/3` allows only the scale; clean up |

### 1.5 Shadow and glass (not in `tokens.json`; values from `F-SPACE.shadow`, `F-COLOR.glass`, `reference/computed/components.md`)

`tokens.json` has no shadow or glass group. Add them as named custom properties in the repo (suggested names below) so call sites never carry raw shadows.

| Suggested token | Pack value | Repo today | Action |
|---|---|---|---|
| `--sh-glass` | `inset 0 1px 0 rgba(255,255,255,.9), 0 18px 40px -30px rgba(17,17,17,.28)` | `--shadow-card: 0 1px 2px rgba(16,24,40,.04), 0 16px 40px rgba(16,24,40,.07)` | retune |
| `--glass-card` | fill `rgba(255,255,255,.78)`, `blur(18px) saturate(1.4)`, 1px `rgba(17,17,17,.07)` | none; **no `backdrop-filter` anywhere in the repo** | add |
| `--glass-panel` | `linear-gradient(180deg,rgba(255,255,255,.78),rgba(255,255,255,.52))`, `blur(26px) saturate(1.45)`, shadow stack incl. `rgba(57,93,237,.34) 0 34px 80px -40px` | none | add |
| `--sh-nav-current` | `0 0 0 1px rgba(17,17,17,.07), 0 6px 16px -10px rgba(17,17,17,.3)` | none | add |
| `--sh-primary-hover` | `0 14px 30px -14px rgba(17,17,17,.6)` | none | add |
| `--sh-prompt` | computed C-PROMPT: 6-layer stack incl. `rgba(57,93,237,.4) 0 44px 100px -28px`, `blur(30px) saturate(1.5)` | none | add |
| `--sh-sheet` | `0 30px 80px -30px rgba(17,17,17,.45), 0 0 0 1px rgba(17,17,17,.06)` | glow-up `0 40px 90px rgba(0,0,0,.5)` | add |
| `--sh-popup` | `inset 0 1px 0 rgba(255,255,255,.95), 0 0 0 1px rgba(17,17,17,.06), 0 50px 100px -40px rgba(17,17,17,.5)` | none | add |
| scrim / backdrop | sheet scrim `rgba(17,17,17,.32)` blur 2px; pop-up backdrop `rgba(232,232,238,.42)` blur 14px | glow-up `::backdrop rgba(17,17,17,.55)` | add |
| ambient light `.amb` | six 48px-blurred circles (blue/spark/violet), full vs quiet light per screen | none (DEC-101 dropped it) | add as one shell component |
| `--g-fill`, `--g-well`, `--g-rim`, `--shadow-well` | (pack has no equivalent) | molten-glass leftovers, set to plain | delete after migration |

### 1.6 Motion (`tokens.json` → `motion`) and layers (`z`)

| Pack | Value | Repo | Value | Action |
|---|---|---|---|---|
| `--mo-press` | 110ms | none | | add |
| `--mo-quick` | 180ms | none | | add |
| `--mo-state` | 260ms | `--t-state` | 0.2s | alias + retune |
| `--mo-move` | 460ms | `--t-reveal` | 0.45s | alias + retune |
| `--mo-scene` / `--mo-hero` | 720 / 1000ms | none | | add |
| `--mo-gap` | 56ms | none | | add |
| `--mo-out` | `cubic-bezier(.16,1,.3,1)` | `--ease-out`, `--ease-move` | same | alias |
| `--mo-emph` / `--mo-acc` / `--mo-snap` | see tokens | none | | add |
| `--mo-spring` | `linear(...)` 16% overshoot | `--spring` | `cubic-bezier(.16,1,.3,1)` (no overshoot; OFFER "never bouncy") | retune (a DEC-101 rule reverses) |
| `--mo-soft` | `linear(...)` 3% | none | | add |
| (none) | | `--t-sp .3s`, `--t-glow 2.4s`, `--slash-skew 0deg`, `--bloom`, `--heat-core` | | delete when their rules go |
| z | ambient −1, sticky 20, sidebar 30, scrim 40, sheet 41, menu 70, pop-up 80, (toast 90, unused: no toasts), effects 2147483000 | `.hdr` z 10; skip link z 10 (globals) / 20 (ds-app) | | add the scale; put the skip link above the sidebar and pop-ups when focused |

### 1.7 Recommended approach: import `tokens.css` as-is, then alias

Import the pack's file unchanged and map the repo onto it, not the other way round.

1. Copy `1pc-handoff/01-foundations/tokens.css` to `apps/web/src/app/tokens.css`, verbatim. Better: generate it from `tokens.json` with a small script (`apps/web/scripts/tokens.mjs`) so the `z`, `space`, `type` and `breakpoint` groups that `tokens.css` leaves out also become variables. `README §6` says a `TOKEN` delta means "change the token, not the call sites"; that only works if the repo uses the pack's names. `V-ACC.visual/2` ("every colour resolves to a token in tokens.json") is also only checkable by name.
2. Add `apps/web/src/app/foundation.css`, hand-written and small: the `--fd`/`--ft` override (below), the `Inter Fallback` face, base settings, type classes, the shadow and glass tokens from 1.5, ambient light, focus ring, `scroll-margin`.
3. Turn the token block of `offer.css` into aliases only: delete `--ink`, `--paper`, `--card`, `--rule`, `--blue`, `--spark`, `--tier-*` there (they collide with the pack's names and offer.css loads later, so it would win), and point old names at the new ones (`--ink-muted: var(--mute)`, `--line: var(--rule2)`, `--line-control: var(--edge)`, `--sunken: var(--sunk)`, `--blue-wash: var(--wash)`, `--ok-dot: var(--okD)`, `--error: var(--badT)` …). Screens move to the pack names as they are rebuilt; then the alias block and `globals.css :root` go.
4. Load order in `layout.tsx`: fontsource → `tokens.css` → `foundation.css` → `globals.css` (legacy, shrinking) → `offer.css` (aliases and components) → `motion.css` → `ds-app.css`.
5. Record the choice in `P-REPO.tokens` and as a BLD decision. It also needs a **product decision superseding parts of DEC-101** (blue `#3355FF`, spark `#FF5B14`, DEC-098 tier hexes, "white cards, hairline rules", "numbered small-capital section labels", "plain text links with an arrow", "never bouncy", no glass). The pack reverses each of these.

**Fonts.** Pack: Google Fonts with `display=swap`, families `Inter Tight` and `Inter`. Repo: self-hosted `@fontsource-variable/inter` 5.3.0 and `@fontsource-variable/inter-tight` 5.3.0 (BLD-D008: no page asks Google, builds work offline), whose families are named `"Inter Variable"` and `"Inter Tight Variable"`. Keep the repo's fontsource packages and do not add a Google link. Because the pack's `--fd`/`--ft` name `'Inter Tight'`/`Inter`, they would not match the fontsource faces and would fall straight to the fallback. So override in `foundation.css`:
`--fd: "Inter Tight Variable","Inter Tight",'Inter Fallback',system-ui,sans-serif; --ft: "Inter Variable",Inter,'Inter Fallback',system-ui,sans-serif;`
and add the pack's `@font-face{font-family:'Inter Fallback';src:local('Arial');size-adjust:107%;ascent-override:90%;descent-override:22.5%;line-gap-override:0%}`. The variable fonts cover every weight the pack uses, including 450 (sidebar items). The result looks identical to the pack; record it as a deviation from `F-TYPE.faces/1`.

**Motion library.** The pack's engine (`reference/css/motion-engine.js`) loads GSAP 3.13 (Flip, SplitText, ScrollTrigger, CustomEase) from a CDN. DEC-101 removed GSAP (BLD-D009 deleted `public/ds/opc.js`), and DEC-100 (Legal on GSAP) fell away. `F-MOTION.build/1–3` allows any library if it is bundled, leaves the GSAP licence `OPEN:` for Legal, and names the fallback: **the Web Animations API plus a FLIP helper**. Screens must still arrive, press and hand over if the library fails. Recommendation: no GSAP, no new dependency.
- `reference/css/motion.css` is already plain CSS: tokens, arrival keyframes (`moIn`, `moInDeep`, `moHead`), presses, primary sheen, opens (`moModal`, `moSheet`, `moMenu`), notes (`moUnfold`), field nudge and OTP shake, track drawing (`moGrowW`, `moPop`, `moBreath`) and reduced motion. Port it as `apps/web/src/app/motion.css`, re-pointing the prototype selectors (`.pc`, `.ph`, `.mtab` …) at the repo's classes and dropping `.snack`/`moToast` (no toasts, `P-DECISIONS.taken/12`).
- GSAP-only parts, rebuilt without it: a ~80-line WAAPI FLIP helper (lists re-sort, layout morph, the sliding choice ring and tab underline); word-by-word hero lines split in React; scroll reveals with `IntersectionObserver`; count-ups with `requestAnimationFrame`; the spark burst as WAAPI on spans in a fixed `pointer-events:none` layer.
- Hand-overs: the prototype uses cross-document `@view-transition`. Next.js App Router navigates client-side, so that rule never fires. Wrap `router.push` in `document.startViewTransition`, or use Next 16's view-transition support (check that it exists on 16.4.5 before relying on it). Skip it under reduced motion.
- For launch, ship the CSS layer (arrivals, presses, opens, nudges, track, skeleton shimmer, sheen) and treat FLIP, hand-overs and sparks as polish.

---

## 2. Component table

State key: **exists, matches**; **exists, differs**; **missing**. Effort is front end unless noted; BE = needs back-end or contract work this pack describes in `05-logic`/`06-contracts`.

| ID | Closest existing file(s) | State | Reuse, enhance or rebuild, and why | Effort |
|---|---|---|---|---|
| `C-AVATAR` | none (no avatars or initials in the app; `components/one-spark.tsx` is a tier spark, not an avatar) | missing | **Build.** Initials disc in 4 sizes, neutral ring, tier ring (conic `--tier-N-ring`), overlapping crew faces with a focusable name tooltip, "1%" system sender. Small, but `C-SIMGRID`, `C-PREVIEW`, `C-CREW-DECK`, `C-QCARD` and `C-INBOX-READER` need it first. **Names on faces conflict with non-negotiable 7** (see risks). | S |
| `C-BUTTON` | `offer.css` `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-quiet`, `.btn-lg`, `.btn-sm`, `.round-btn`, `.back`; legacy `globals.css` `.button`, `.button-secondary`, `.link-button` (used in **26 TSX files**: review, committee, delivery, admin, ember, learning, appeals …) | exists, differs | **Enhance in place.** Ink primary, white line button with `--edge` ring and quiet text button are all there. Changes: radius 10 → 12; full 56px / small 44px sizes; add `soft` and the underlined `.tb` text button (`#A3A3A6` underline, 4px offset) plus `.tb.blue`; disabled is `--rule2` fill with `#6B6B70` text, not `opacity:.5`; press scale .97 and the primary sheen; busy state (spinner + "Sending…", width kept). Map the variant names (`ink`→`btn-primary`, `line`→`btn-secondary`, `tb`→`btn-quiet`) instead of renaming call sites. Move the 26 legacy `.button` files to `.btn`: today they paint **blue filled** primaries, which breaks "one ink primary". Then delete `.button`. | M (CSS S; migrating 26 files M) |
| `C-CARD` | `offer.css` `.glass`, `.idea`, `.match` (flat white, 1px `--line`, r20); `.status-soon`/`.soon-pill` (dashed); `.jersey` (dark); `globals.css` `.card`, `.panel`, `.stack-form`; `ds-app.css` `.home-route`, `.scan`, `.empty-note` | exists, differs | **Enhance.** The class called `.glass` is a flat white card, because DEC-101 took the glass out. Add the pack's surfaces: glass card inside the shell (solid on signed-out pages), glass panel, tile, well, note (plus the blue note), dark slab (`--slab`, r28, tier glow), dashed placeholder. Keep the whole-card link with one focus ring (`.idea:has(a:focus-visible)` already does `C-CARD.rules/4`). Glass needs the ambient layer behind it (`C-CARD.rules/5`). Retire `globals .card` and `.panel`. | M |
| `C-CHIP` | `offer.css` `.choice`/`.check` (labels wrapping native radio/checkbox inputs, 48px, blue ring when checked); `ds-app.css` `.canvas .choice` (pill-shaped canvas chips) | exists, differs | **Enhance; keep native inputs.** A native radio group already gives the `radiogroup`/`radio` roles and arrow keys (`F-A11Y.rules/10`) with no script. Restyle to the pack: 40px desktop / 44 phone, 14–14.5px, hide the drawn radio circle and show a leading tick when selected, text `--blueT` (repo uses raw `#2340d8`), press .97. Add filter chips (single choice with "All" and live counts) and the trailing "Search all areas" text button. The sliding selection ring needs the FLIP helper (polish). | M |
| `C-CREW-DECK` | `app/share/[id]/done/crew.tsx` (Find your crew as a vertical list of `.match.crew-card` on the scan page), `ds-app.css` `.crew-cards` | exists, differs | **Rebuild.** The pack makes it a stacked deck on its own screen (`S-H2` `/crew`): 440×540 card, pass/next flight, pager, ← →, filter panel, "Your crews", empty/everyone-seen states. Reuse crew.tsx's team-up POST call, its error map and the e2e intent (`.crew-card` locator). **Card content (names, "the problem, in their words") conflicts with non-negotiable 7.** | L (+BE `L-CREW` ordering, filters) |
| `C-DRAFT-LOADER` | `app/share/[id]/done/scan-status.tsx` `.scan-steps` (sequential gatekeeper → canvas assist → matching steps, polled, breathing dot) | missing | **Build new.** Different model: six parallel parts streaming, weighted progress `0.9×(1−e^(−t/mean))` capped at 97%, ETA line, slow-part line, failure defaults, `role="progressbar"` updated at most once a second. Keep scan-status's reduced-motion handling and polite live region. Needs `A-API.draft-stream` and per-part p50 means from monitoring. | M (BE: streaming endpoint, per-part means) |
| `C-DRAFT-PANEL` | `app/share/[id]/canvas-form.tsx` (six-section canvas with a strength meter); crew.tsx "Check your canvas" (suggestion next to the person's own words, DEC-095) | missing | **Build new.** A live document with fixed slots, part states (Waiting, Updating, Filled, Your call, Editing), a "why" line, phrase highlighting, a pinned "Move to Review" footer, and a phone peek sheet. Reuse DEC-095's quote-to-phrase mapping (`from-words`) and `lib/canvas/rules.ts` validation. The canvas form and strength meter have no place in the pack. | L (BE `L-DRAFT.parts`, pins) |
| `C-DROPDOWN` | none (native `<select>` only, e.g. review filters) | missing | **Build.** Field-looking disclosure button (`aria-expanded`, `aria-controls`) over a checkbox group with title and meta rows; "None picked", "2 ideas picked"; Escape closes the list only; chevron turns. | S |
| `C-EMPTY` | ad hoc: `my-ideas/page.tsx` `p.glass.empty-note`, `wall/page.tsx` `p.muted` per section, `inbox/page.tsx` plain `<p>` | exists, differs | **Build a small component** (title h3, one or two lines, at most one action; centred in a card, left in a list) and replace the ad hoc lines. Copy comes per screen from `reference/copy/`. | S |
| `C-FIELD-MSG` | `globals.css` `.field-error` (bold red text, no tint, no icon); `components/status.tsx` (`Status` error/check/soon with a glyph, page-level) | exists, differs | **Enhance.** Add a `FieldMsg` component: tinted note under the field, 16px leading icon, `--badW`/`--badT` or `--warnW`/`--warnT` with the inset ring, `role="alert"`, wired through `aria-describedby`, drops in 280ms and nudges once. Reuse the glyph from `Status`. Keep `Status` for page-level load failures ("We can't load your ideas just now") restyled as a `C-CARD` note. Delete the canvas `.error-summary`: the pack puts messages under fields, never at the top (`C-FIELD-MSG.behaviour/1`). | S |
| `C-FIELD` | `offer.css` `.field`, `.input`, `.textarea`, `.select`; `ds-app.css` `.canvas .field textarea/input` (52px, 17px); `globals.css` bare `input`, `label` | exists, differs | **Enhance via tokens.** Border `#D0D0CB` → `--fieldBorder` `#8C8C91` (**repo fails 3:1 today**); radius 12; focus = blue border + `0 0 0 3px rgba(57,93,237,.16)` ring; invalid = `--badT` border + red ring; textarea min 112; label 500 15/1.4 with "Optional" in `--mute`; placeholder `#6B6B70`; help line slot. **New:** six-box code field (`S-02` email-code route; the repo signs in by Entra SSO only, so `L-AUTH`'s email code is a new back-end route) and the question box with "Pinned to <part>". | S (+M for code field and question box) |
| `C-FILE` | `app/share/[id]/attachments.tsx` (upload to quarantine, polling `quarantine → processing → awaiting_check → clean/rejected`, plain-words state, Remove) | exists, differs | **Enhance; keep the logic.** The quarantine, scan and poll state machine is right and stays. Build the pack's row (type badge, name, size, status, actions) and the drop area with browse, paste and folder. **Links:** the "Link unreachable" state means checking reachability (`L-HIDE.files/7`), which conflicts with **non-negotiable 8** ("links are never fetched"). "Hide it for me" (black out the region in the stored copy) and "View" need worker support. Type list and limits differ (pack: Markdown, HTML, ZIP, folders, 15 or 25 MB; repo: pdf, docx, pptx, xlsx, csv, png, jpg from config). Build one configurable list (`P-DECISIONS.open/12`). | M (FE) / L incl. BE |
| `C-HIDDEN` | `canvas-form.tsx` `.pd-note` (blocks personal data in the text); `scan-status.tsx` blocked spans with "contest" (BLD-082) | exists, differs | **Rebuild, but ask first.** The pack masks a customer detail ("Folio ••••89") and lets the sharer **show it** with a reason. **Non-negotiable 4** says pattern blocks on investor and customer identifiers are absolute. Product owner and InfoSec decide before this is built. | M (BE `L-HIDE`) |
| `C-INBOX-READER` | `app/inbox/message-list.tsx` (accordion of plain-text messages, mark read on open), `globals.css` `.inbox` | exists, differs | **Rebuild.** Two-pane reader with "Today / This week / Earlier" groups, typed kinds with their own body (a `C-QCARD`, merge request, decision), a pinned footer of actions, "1 of 9" prev/next, archive in "More", countdowns. Reuse the mark-read call and the `plain()` sanitiser (template Markdown never becomes HTML). E2E `.inbox li` needs updating. | L (BE `L-INBOX.kinds`) |
| `C-LISTEN` | none | missing | **Build new.** Glass player: play/pause, speed cycle, part ticks, seek, "Save for offline". The audio is a new back-end service (`L-LISTEN`, text-to-speech) that must speak hidden details as "hidden" and stay inside the gateway and tagging rules. A **cut candidate** for 20 Nov. | M FE / L BE |
| `C-ONES-FAN` | `components/ones-carousel.tsx` (dark band, sideways strip, prev/next, opt-in autoplay, reduced-motion hook), `components/one-card.tsx` (`OneCardBody` jersey) | exists, differs | **Rebuild the interaction, reuse the parts.** Keep the reduced-motion hook, prev/next buttons and "N of M" semantics; drop autoplay. Build the stacked-to-spread fan, wheel stepping that hands the scroll back to the page at either end, tilt, and the 341×511 post card (avatar with tier ring, sentence, Shipped pill, big figure, like/thread/comment counts). Separately, the **jersey card is reusable for the Wall's Ones cards** (`L-WALL`: tier bar, flag, number, name, "Tier 4, Blaze", brief); retune its radius and `--slab`. Keep the consent rule: a name only if the One said yes, else "One No. 17". | M–L (BE `A-API.ones-posts`) |
| `C-PILL` | none as a component (stage shows as `dt`/`dd` text); `globals.css` `.state` (admin on/off), `.badge`; `offer.css` `.soon-pill` | missing | **Build.** Dot + words, 26px, five variants plus "on a gradient band" and outline "Coming soon". The status-to-variant mapping comes from `E-ENUMS.idea-status`, never chosen per screen. Note: the computed "blue" sample (`rgb(211,219,255)` on `rgba(57,93,237,.28)`) is the on-band variant; build the standard blue from the spec table. | S |
| `C-PREVIEW` | `app/my-ideas/glow-up.tsx` is the only modal, built on native `<dialog>` + `showModal()` | missing | **Build on the glow-up's native-dialog pattern.** `showModal()` puts the pop-up in the top layer, which satisfies `F-COLOR.glass/3` (never inside a glass container) and makes the background inert. Add backdrop-click close, focus return to the opener, 560px glass with gradient band (hue 1/2), "Why it matches", sharer vs reviewer sections, a single footer button that hands over to `C-SHEET-TEAMUP`/`C-SHEET-MERGE`. **"The problem, in their words" and the lead's name conflict with non-negotiable 7.** | M |
| `C-PROMPT` | `app/share/start.tsx` (quick vs full choice), quick-capture textarea in `canvas-form.tsx`, `voice-recorder.tsx` (record ≤3 min → quarantine → scan → worker transcript into the box, DEC-096), `attachments.tsx` | exists, differs | **Rebuild the box; reuse voice and upload.** New frosted box (r28, `--sh-prompt`), growing input, tool row (attach, mic, round send), help line, starters, live sorting guess, Enter sends / Shift+Enter new line, `P` focuses it. Keep the voice pipeline. `L-DRAFT.voice/2` asks for **live** words while speaking; the browser's own speech recognition would send audio to a third party, so live recognition needs a server route through the gateway. Until that is agreed, show the transcript when recording stops. The mic is on Home too: `next.config.ts` allows the microphone only on `/share/*` (`PERMISSIONS_POLICY_SHARE`), so Home and Answer need the policy widened, with `tests/unit/security-headers.test.ts` updated. | L (BE live transcription if approved) |
| `C-QCARD` | none; the reviewer can ask one question (`app/review/[id]/actions.tsx` "Ask the person a question"); `scan-status.tsx` shows `question {text, due}` | missing | **Build.** Header with reviewer and countdown pill, numbered questions each pinned to a part, deadline line, one button to Answer. States: waiting, partly answered, answered, overdue. Today the back end supports a single question, not several pinned ones (`L-QUESTIONS`). | M (BE) |
| `C-SEARCH` | none (`app/review/page.tsx` has a GET filter form with selects) | missing | **Build.** Glass bar with chips inside, suggestions panel with live counts, Backspace removes the last chip, state kept in the URL and restored on Back. "Search by meaning" and "answer a question in one line" are model calls: they go through the gateway, and the review desk's notes must be filtered by RLS for a sharer. A plain filter + text search first is a launch-safe cut. | M FE / L BE |
| `C-SHEET-MERGE` | none (cluster proposals in `app/review/clusters/[id]/proposal-actions.tsx` are a different flow) | missing | **Build** on the native-dialog pattern: solid white 560px sheet, "Which idea leads" choice rows, "Team them up" tick, pre-filled note (≥20 chars), one button "Merge and tell both", banner after. | M (BE `L-MERGE.desk`) |
| `C-SHEET-TEAMUP` | `crew.tsx` inline team-up form per card (one line + details, 30/50-character minimums, server error map) | exists, differs | **Rebuild as a dialog; reuse POST and validation.** Pre-filled note drafted from the person's idea (a gateway call), hint states, `C-DROPDOWN` "Bring your ideas along", privacy line, sent state with spark, Withdraw. Check-it variant: "Ask {lead} to merge mine in" / "Keep mine separate". The repo's error copy uses "Please", which `F-COPY.voice/6` drops. | M |
| `C-SIMGRID` | `crew.tsx` match cards (only after sending, on the scan page) | exists, differs | **Rebuild.** Tiles on Check it before sending, "Yours, not sent yet" first, 3/2/1 columns, "Show more", fold-to-note after "Keep mine separate"; list form for the reviewer; one quiet line in the draft panel. **Tiles show the lead's name and crew faces: non-negotiable 7** (repo shows only `neutral_summary`, area, stage and count, per DEC-026). | M |
| `C-SKELETON` | none (only `aria-busy` on a few buttons) | missing | **Build.** Bars at the exact size of their content, `#E9E9E6 → #F1F1EE` shimmer (blue-tinted inside the loader), fade-in arrival, 12px spinner for buttons and inline status only, `aria-busy` + polite status, still under reduced motion. | S |
| `C-SORTS` | none | missing | **Build.** `role="group"` of `aria-pressed` buttons, 32px with a 44px touch hit area, state in the URL, phone "Sorted by …" cycling button with a polite announcement. Row gliding needs the FLIP helper (polish). | S |
| `C-TABS` | none | missing | **Build.** `tablist`/`tab`/`tabpanel`, arrow keys, count badges, ink underline that slides (FLIP or CSS anchor), URL-synced, zero-count tabs stay. | S–M |
| `C-TRACK` | `app/ideas/[id]/page.tsx` `Timeline` (an `ol` of events); `scan-status.tsx` step dots | missing | **Build.** Five fixed stages (Shared, Checked and matched, Reviewed, Built, Shipped) as an ordered list with state suffixes, horizontal on desktop and vertical on phone, detail lines, draw-in motion. Keep the event `Timeline` as history; the track is new. Stage words differ from the repo's stage strings, so a mapping from `E-ENUMS` is needed. | S–M |
| `C-WORTH` | `canvas-form.tsx` `ESTIMATE_FIELDS` (hours a month, ₹ saved a year, ₹ one-time, ₹ revenue a year, clients who would pay) with `parseFigure`; reviewer "edit" in `review/[id]/actions.tsx` | exists, differs | **Rebuild the view; reuse figure parsing.** Pack measures: time a month, cost a month, revenue a month, outside tools (No change / Partly / Fully). The sharer side becomes "What it would bring" chips. The reviewer revision shows "was …" next to the original. Field set and units differ from the repo's model (a contract change). | M (contract) |

Summary: **reusable with enhancement** are `C-BUTTON`, `C-CARD`, `C-CHIP`, `C-FIELD`, `C-FIELD-MSG`, `C-FILE` (logic), `C-EMPTY`, plus parts of `C-PROMPT` (voice, upload), `C-SHEET-TEAMUP` (POST, validation), `C-ONES-FAN` (jersey, carousel controls), `C-INBOX-READER` (read API, sanitiser) and `C-WORTH` (figure parsing). **Wholly new**: `C-AVATAR`, `C-PILL`, `C-SKELETON`, `C-SORTS`, `C-TABS`, `C-TRACK`, `C-DROPDOWN`, `C-SEARCH`, `C-PREVIEW`, `C-SHEET-MERGE`, `C-QCARD`, `C-LISTEN`, `C-DRAFT-LOADER`, `C-DRAFT-PANEL`, `C-SIMGRID` (as a pre-send grid), `C-CREW-DECK` (as a deck), `C-HIDDEN` (as masking).

---

## 3. Accessibility

### 3.1 What the repo already has, which new components must keep

| Have | Where | Keep how |
|---|---|---|
| axe in CI on every suite: `expectNoSeriousAxeIssues` with tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` (serious and critical only), 29 call sites | `apps/web/e2e/helpers.ts`, `.github/workflows` → `make e2e` | Run it on every new component state (open sheet, open preview, filled draft panel, error states) |
| Reflow check on every axe call: no sideways page scroll at the viewport width and at 320px (BLD-A163); Playwright projects `desktop` and `phone-360` | `e2e/helpers.ts` `expectNoSidewaysScroll`, `playwright.config.ts` | Decks, fans, chip rows and tile grids must scroll inside their own box, never the page |
| Visible focus: `:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px }`; one card-level ring for whole-card links (`.idea:has(.idea-title a:focus-visible)`) | `offer.css` | Keep; offset changes to 3px (3.2) |
| Skip link, `main#main tabIndex=-1`, `nav aria-label="Main"`, `lang="en-IN"` | `layout.tsx`, `components/nav.tsx` | The sidebar keeps `nav` "Main"; the skip link must sit above it |
| Reduced motion: a global CSS stop (two copies, `globals.css` and `offer.css`); JS guards in `ones-carousel.tsx` (no autoplay, `scrollTo` "auto"), `glow-up.tsx`, `launch/stage.tsx`, `constellation/sky.tsx`; `e2e/launch.spec.ts` runs with `reducedMotion: "reduce"` | as listed | Every WAAPI, FLIP, view transition and effects-layer call needs the same guard (CSS cannot stop them) |
| Native controls and roles: native radios/checkboxes inside `.choice`; `aria-disabled` (focus kept) while busy; `role="timer"` with `aria-live="off"` on the voice clock; polite `role="status"` lines for save and scan state; `role="alert"` errors | `voice-recorder.tsx`, `canvas-form.tsx`, `scan-status.tsx`, `attachments.tsx` | Same patterns in `C-BUTTON` (disabled and busy), `C-FIELD-MSG`, `C-DRAFT-LOADER`, `C-QCARD` countdown |
| Modal done right once: native `<dialog>` + `showModal()`, `aria-labelledby`, Escape handled in `onCancel`; `inert` on the page behind full-screen overlays | `my-ideas/glow-up.tsx`, `launch/stage.tsx`, `constellation/sky.tsx` | Base `C-PREVIEW`, `C-SHEET-MERGE`, `C-SHEET-TEAMUP` on it |
| Never colour alone: `Status` glyph + words; tier colour never as text, enforced by a unit test | `components/status.tsx`, `tests/unit/tier-colour-text.test.ts` | Pills are dot + words; tier rings and bars only |
| Tables stack into blocks under 40rem; strips scroll inside themselves with `tabIndex=0` and a region label | `globals.css` `.table`, `ones-carousel.tsx` | Keep for admin and review tables |
| Microphone allowed only where it is used | `next.config.ts` Permissions-Policy | Widen deliberately for Home and Answer (`C-PROMPT`) |

### 3.2 What `F-A11Y` asks for that the repo lacks

1. **WCAG 2.2 AA**, not 2.1 AA (CLAUDE.md non-negotiable 10 says 2.1). Add `wcag22aa` to the axe tags (brings in `target-size`, 2.5.8). `V-ACC.visual/4` wants no axe violations at all, but the helper only fails on serious and critical.
2. **Field and control borders at 3:1.** Fields today use `--line-control` `#D0D0CB`, about 1.5:1 on white (`offer.css .input/.textarea/.select`, `ds-app.css .canvas .field …`). This fails 1.4.11, and axe does not test non-text contrast, so CI never caught it. The pack's `--fieldBorder` `#8C8C91` fixes it. The pack itself still draws chips and line buttons with `--edge` `#D0D0CB`; their text identifies them, but measure them and raise it with the designer.
3. **Focus not obscured** (2.4.11): `scroll-margin-block: 96px 140px` globally (16/120 in the phone scroll area) before any sticky task bar, sidebar or dock ships. Focus offset 3px, eased in over `--mo-quick`.
4. **Dialogs**: focus in on open, trapped, back to the opener on close, backdrop click closes, `aria-modal`, `aria-labelledby`/`describedby`. There are none yet apart from the glow-up.
5. **Composite widgets the repo has never needed**: tabs (`tablist`/`tab`/`tabpanel` + arrows), `aria-pressed` groups (sorts, multi-choice chips), `role="progressbar"` with throttled `aria-valuetext` (draft loader), a checkbox group in a disclosure (dropdown).
6. **Keyboard shortcuts**: `P` from anywhere must be ignored while typing and switchable off (WCAG 2.1.4); Enter sends, Shift+Enter new line, and the prompt box says so; ← → in the deck and fan with button alternatives (`F-A11Y.rules/11`).
7. **Targets**: 44×44 everywhere; the 40px desktop chips and 32px sort options need a padded 44px hit area on coarse pointers (`F-SPACE.targets/2`).
8. **Text spacing and 200% zoom**: the repo tests reflow at 320px but not text-spacing overrides. The pack's fixed heights (26px pill, 40px chip, 46px tab) must be `min-height`.
9. **Contrast on glass over ambient light** (`F-COLOR.contrast/1`): there is no glass yet. Add a token-pair contrast test (like the email tests that compute AA) against the lightest and darkest the glass can get.
10. **Reduced motion is stricter**: `V-ACC.visual/6` ("no element changes position or opacity after first paint, no hand-over plays") also covers script-driven motion.
11. **Live announcements**: one polite announcement per draft part that fills, per count change and per sort change; countdowns as `role="timer"` that do not tick aloud.
12. **Brand mark name**: `F-A11Y.rules/16` says the mark is named "1% Club". The repo hides it when the word "1% Club" sits beside it, which avoids reading the name twice. Keep that, and name it only where it stands alone.
13. **Check**: one `h1` per screen. Several repo pages style the title as `.t-display`; check the level when screens are rebuilt.

---

## 4. Repo CSS and components with no place in the new design (candidates to delete)

Delete each one only when the component or screen that replaces it lands, and update the e2e locators that name it.

| Candidate | Where | Why | Blocks / locators |
|---|---|---|---|
| `globals.css :root` (Zed, Electric, Graphite, Ash, Slate, Geist `var(--font-geist-*)`) and the legacy alias block in `offer.css` (`--zed`, `--electric*`, `--graphite`, `--ash-lit`, `--slate`, `--line-dark/light`, `--bg`, `--text`, `--accent`, `--border`, `--g-fill`, `--g-well`, `--g-rim`, `--shadow-well`, `--heat-core`, `--bloom`, `--slash-skew`, `--t-glow`, `--line-soft`, `--error-line`) | `apps/web/src/app/globals.css` 1–25, `offer.css` 48–108 | Pre-OFFER and molten-glass names; Geist was removed in BLD-D008, so `--font-geist-*` resolves to nothing | Remove once every rule reads pack names |
| `.button`, `.button-secondary`, `.link-button`, `.notice`, `.notice-error`, `.card`, `.panel`, `.state`, `.badge`, `.brand-band` | `globals.css` | A second button system (blue-filled), old notices and pills. Superseded by `C-BUTTON`, `C-CARD`, `C-PILL`, `C-FIELD-MSG` | 26 TSX files use `.button`; migrate, don't drop |
| Dead classes (no TSX reference): `.one-card`, `.one-card-top`, `.one-number`, `.one-name`, `.one-tag`, `.one-muted`, `.tier-dot`, `.measure-chips`, `.round-button`, `.strength-bar` | `globals.css` (around 626 and 1066–1170) | Already unused | none |
| `.eyebrow` (numbered small-capital labels) and `.btn-sm` | `offer.css` 261, 302 | Unused in TSX; the pack forbids caps and letter-spaced labels (`F-TYPE.rules/1`) | none |
| Strength meter: `.slashes`, `.slash`, `.strength*` | `offer.css` 798–816, `ds-app.css` 1041–1103, `canvas-form.tsx` | The pack has no strength meter: Tell it + `C-DRAFT-PANEL` replace the canvas | e2e `.strength-score`, `.strength ol li` |
| Canvas `.error-summary` | `canvas-form.tsx`, `offer.css .summary` | The pack puts messages under fields, never at the top | |
| Header lockup and top nav: `.hdr*`, `MainNav`, the ds-app header rules, `.site-footer` (check against the boards) | `offer.css` 924–1024, `ds-app.css` 56–180, `components/nav.tsx`, `layout.tsx` | `F-SPACE.shell/4`: no top bar on signed-in desktop; `C-SIDEBAR`/`C-PHONE-TABS` replace it (another agent's scope) | e2e `.site-header`, `.account-name`, `.site-footer` |
| Ones carousel autoplay and play/pause | `components/ones-carousel.tsx` | `C-ONES-FAN` has no autoplay | e2e `.ones-band` (Wall) |
| Three-route Home (`.home-routes`, `.home-route-slash`) | `app/page.tsx`, `ds-app.css` 197–297 | Home is prompt-first (`S-03`, `C-PROMPT`) | |
| Dark `[data-theme="zed"]` bands on Sign in, the Wall's top and the Ones carousel | `sign-in/page.tsx`, `wall/page.tsx`, `ones-carousel.tsx`, entry rules in `ds-app.css` 408–535 | The pack puts these on paper with full ambient light. Dark stays only for the slab (Wall Ones, One dashboard hero), the glow-up, Office and Launch | |
| Dead molten-glass attributes `data-lit` (9), `data-glow` (6), `data-edge` (2), `data-refract` (2), `data-tilt` (2, set by `jerseyProps`) | TSX across `app/` and `components/` | No stylesheet reads them any more | none |
| Duplicate helpers: `.vh` and `.visually-hidden`; two reduced-motion blocks | `offer.css`, `globals.css` | Keep one of each | |
| Middle dots between meta items (15 TSX places, plus `chip-links` separators) | e.g. `ideas/[id]/page.tsx` Timeline, `my-ideas/page.tsx` | `F-TYPE.rules/3`: commas, not middle dots | |
| SparkMark's "small cut" (< 32px: heavier zeros, no dot) and its 12px stroke / r7 dot | `components/spark-mark.tsx` | `F-ICONS.mark`: one geometry (stroke 14, dot r9), never redrawn. Confirm with the product owner before dropping the small cut | |
| `docs/design/system/` (`tokens.json`, `bundle.css`, ABOUT/HANDOFF/MOTION…) | docs | A pre-OFFER snapshot (Electric `#2b5bff`, Zed) that now contradicts both DEC-101 and the pack; mark it superseded so no one builds from it | |

Keep, but restyle rather than delete: `components/status.tsx` (page-level notes), `.status-soon`/`.soon-pill` (becomes the outline pill and dashed placeholder), `one-card.tsx` jersey (Wall and One dashboard cards), `glow-up.tsx` (the pack keeps the glow-up in `S-ONE`), and the admin, delivery, learning, presentations, Ember, lenses, reports and console screens. The pack draws no screens for these, but `README §9.5` asks for minimal admin pages, so they need the button and field migration, not removal.

---

## 5. Risks to raise before building

1. **Non-negotiable 7 (submitters never see another person's raw text or name).** `C-SIMGRID`, `C-PREVIEW`, `C-CREW-DECK`, `C-SHEET-TEAMUP` and `C-AVATAR` crew faces show the lead's name, crew names and "The problem, in their words". The repo deliberately shows only `neutral_summary`, area, stage and count (DEC-026, `crew.tsx`). Stop and ask.
2. **Non-negotiable 4 (pattern blocks are absolute).** `C-HIDDEN` masks investor and customer details and lets the sharer "Show it". Stop and ask (product owner and InfoSec).
3. **Non-negotiable 8 (links are never fetched).** `C-FILE` "Link unreachable" needs a reachability fetch (`L-HIDE.files/7`), which is also an SSRF surface. Stop and ask.
4. **Live voice recognition** (`L-DRAFT.voice/2`) cannot use the browser's speech service without sending audio outside the gateway. Keep record-then-transcribe until a server route is agreed. The mic also needs the Permissions-Policy widened beyond `/share`.
5. **DEC-101 is reversed in many places**: glass, ambient light, blue, spark, tier hexes, spring overshoot, no caps labels, no arrows. That needs a recorded product decision, plus coordinated changes in `services/worker/ones/tiers.py`, the email marks and templates (BLD-A170) and `docs/BRAND.md`.
6. **Performance of glass.** Every shell card uses `backdrop-filter: blur(18–30px)` over six 48px-blurred light layers. Test on a typical KFin office PC or VDI before committing; the quiet-light screens help.
7. **Time.** Four working days to 20 November and about 17 wholly new components. A launch-safe order: tokens and foundation → `C-BUTTON`, `C-FIELD`, `C-FIELD-MSG`, `C-CHIP`, `C-PILL`, `C-CARD`, `C-SKELETON`, `C-EMPTY`, `C-AVATAR`, `C-TRACK`, `C-TABS`, `C-SORTS` → share-journey components. Cut or simplify `C-LISTEN`, semantic `C-SEARCH`, the deck and fan physics, FLIP, hand-overs and sparks.
8. **Pack gaps**: `tokens.json` has no shadow or glass group (taken from prose and `reference/computed/`), and `tokens.css` leaves out space, z, type and breakpoints. Generate them from `tokens.json` so future `TOKEN` deltas apply cleanly.
