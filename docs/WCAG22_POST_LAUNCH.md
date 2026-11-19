# WCAG 2.2 AA: the post-launch list

At launch the accessibility gate is WCAG 2.1 AA (non-negotiable 10; DEC-112, product lead, 19 Nov 2026). This list holds what axe's WCAG 2.2 rules found on `main` before launch. Nothing on it blocks the 14:00 gates, the go/no-go or launch. Lane A keeps the list; each item names the lane that owns the screen.

## How it was found

On 19 Nov, CI run 44398344925 ran the full gates on the throwaway branch `a/verify-wcag22-inventory` (fdd0fc9f, on `main` a433c881). That branch is never merged. It made every axe check in `apps/web/e2e/` run a second pass with only the `wcag22a` and `wcag22aa` tags and log what it found, without failing the test. The run covered 316 passing tests on desktop and on a 360 px phone. One test was flaky: S-05's axe test in `check-it.spec.ts`, where the second pass pushed it past its 30-second limit (it takes 16.5 s on `main`). Lane G's journey suite was not part of this run.

## What axe found

Every finding is the same rule: target size, WCAG 2.5.8, rated serious. In each case axe says the target is partially obscured: something else on the page overlaps it where axe measured it, which leaves a free strip under 24 px high. The drawn target may itself be big enough, so look at each one in the browser before changing a size. The fix is more likely the overlap: spacing, stacking order or a sticky bar.

| # | Screen and owner | Route | Element | Free space axe measured (needs 24 × 24 px) |
|---|---|---|---|---|
| 1 | S-02 Sign-in (lane A) | `/sign-in` | The 1% Club mark that links to Landing, `.si-brand` (`app/sign-in/page.tsx`) | 96.8 × 8 px |
| 2 | S-05 Check it (lane C) | `/share/:id/check` | The "Change title" button (`app/share/[id]/check/parts.tsx`) | 56 × 10.2 px |
| 3 | S-R2 The idea at the desk (lane B) | `/desk/ideas/IDEA-2026-000050` and `…000051` | The link to IDEA-2026-000049 on the panel | 232 × 13.4 px |
| 4 | S-H2 Find your crew (lane F) | `/kit/crew`, the kit page that renders the crew screen | The filter button, `.crew-fbtn` (`app/crew/crew-screen.tsx`) | 103 × 6.4 px. **Cause found, not a fix (lane F, 20 Nov, BLD-F093):** nothing overlaps the button at rest. By the log's timing in run 44398344925, axe measured it at 375 px in `find-your-crew.spec.ts`'s J-TEAMUP test, after the tap on the card's Team up had scrolled the page, so the button sat under the phone's sticky bar (`.pnav`, whose back link fills its 1fr column). A sticky bar covers whatever scrolls under it, so no change keeps the look (DEC-119). Pinned at rest by an axe `target-size` check at desktop and 360 px in the same spec. For BLD-A229: that test's page-level axe call still runs at that scroll |

## What axe does not check

axe tests only target size among the success criteria WCAG 2.2 adds at levels A and AA. The others need a person to check them, screen by screen, before the gate moves to 2.2:

- 2.4.11 Focus Not Obscured (Minimum). One case is already fixed: S-H2B's result line is scrolled into view after an answer (BLD-A228).
- 2.5.7 Dragging Movements.
- 3.2.6 Consistent Help.
- 3.3.7 Redundant Entry.
- 3.3.8 Accessible Authentication (Minimum).

## Turning the 2.2 gate on after launch

Once the four items above are fixed, BLD-A229 is a single change in `apps/web/e2e/helpers.ts`: add `"wcag22a"` and `"wcag22aa"` to the `withTags` list. Land it on a branch whose CI is green, and only after the product lead agrees, since DEC-112 holds the gate at 2.1 AA for launch.
