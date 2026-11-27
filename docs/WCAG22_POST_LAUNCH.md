# WCAG 2.2 AA: the post-launch list

At launch the accessibility gate is WCAG 2.1 AA (non-negotiable 10; DEC-112, product lead, 19 Nov 2026). This list holds what axe's WCAG 2.2 rules found on `main` before launch. Nothing on it blocks the 14:00 gates, the go/no-go or launch. Lane A keeps the list; each item names the lane that owns the screen or the shared component.

## How it was found

On 19 Nov, CI run 44398344925 ran the full gates on the throwaway branch `a/verify-wcag22-inventory` (fdd0fc9f, on `main` a433c881). That branch is never merged. It made every axe check in `apps/web/e2e/` run a second pass with only the `wcag22a` and `wcag22aa` tags and log what it found, without failing the test. The run covered 316 passing tests on desktop and on a 360 px phone. One test was flaky: S-05's axe test in `check-it.spec.ts`, where the second pass pushed it past its 30-second limit (it takes 16.5 s on `main`). Lane G's journey suite was not part of this run.

## What axe found

Every finding is the same rule: target size, WCAG 2.5.8, rated serious. In each case axe says the target is partially obscured: something else on the page overlaps it where axe measured it, which leaves a free strip under 24 px high. The drawn target may itself be big enough, so look at each one in the browser before changing a size. The fix is more likely the overlap: spacing, stacking order or a sticky bar.

| # | Screen and owner | Route | Element | Free space axe measured (needs 24 × 24 px) |
|---|---|---|---|---|
| 1 | S-02 Sign-in (lane A) | `/sign-in` | The 1% Club mark that links to Landing, `.si-brand` (`app/sign-in/page.tsx`) | 96.8 × 8 px |
| 2 | S-05 Check it (lane C) | `/share/:id/check` | The "Change title" button (`app/share/[id]/check/parts.tsx`) | 56 × 10.2 px |
| 3 | C-SIDEBAR, the review desk's "Waiting on sharers" list (lane D) | `/desk/ideas/IDEA-2026-000050` and `…000051`, where the open sidebar shows it | The list's row that links to IDEA-2026-000049, `a[href="/desk/ideas/IDEA-2026-000049"]` (`components/shell/sidebar.tsx`), sliding under the account row | 232 × 13.4 px |
| 4 | S-H2 Find your crew (lane F) | `/kit/crew`, the kit page that renders the crew screen | The filter button, `.crew-fbtn` (`app/crew/crew-screen.tsx`) | 103 × 6.4 px. **Closed 26 Nov, not a product defect (see "Where they stand").** **Cause found, not a fix (lane F, 20 Nov, BLD-F093):** nothing overlaps the button at rest. By the log's timing in run 44398344925, axe measured it at 375 px in `find-your-crew.spec.ts`'s J-TEAMUP test, after the tap on the card's Team up had scrolled the page, so the button sat under the phone's sticky bar (`.pnav`, whose back link fills its 1fr column). A sticky bar covers whatever scrolls under it, so no change keeps the look (DEC-119). Pinned at rest by an axe `target-size` check at desktop and 360 px in the same spec. For BLD-A229: that test's page-level axe call still runs at that scroll |

Item 3 was first put down as a link on S-R2's panel (lane B). It is not: S-R2's similar-idea title is a button, and the obscured link is a sidebar row, 232 px wide in the 256 px bar (lane B, 21 Nov).

## Where they stand (21 Nov, `main` b1d4e341)

Lane D's BLD-D018 (WCAG 2.5.8 in the shared shell and components) landed in lane E's train 2. CI 44805347398 is green on `b1d4e341`. Lane D's verify run 44790888663 put the same 2.2 logger on its branch (`d/verify-targets-1`, 7d343fd9). It found one target where run 44398344925 found five. The table gives each item's count before and after.

| # | Before → after | Where it stands |
|---|---|---|
| 1 | 1 → 0 | **Fixed** (BLD-D018). The focused skip link covered `.si-brand`, because the smoke test presses Tab before axe runs. With focus, the skip link now takes its own row in the page flow (`app/ds-app.css`, `app/shell.css`). |
| 2 | 1 → 0 | **Not a product defect.** C-TASKBAR's sticky "Save and close" covered the button at scrollY 299, where Playwright's click on Submit left the page. The app scrolls nothing there, and `scroll-margin-block` keeps keyboard focus clear (F-SPACE.scroll/1). It reads 0 only because main's longer file line (BLD-C199) moved where that click leaves the page; it can come back if the layout shifts. |
| 3 | 2 → 0 | **Fixed** (BLD-D018). `.sb-sec { min-height: 0 }` let the last row slide under the account row in a 720 px window. The open bar's sections now keep their full height and the bar scrolls (`app/shell.css`). Lane B's P2 (BLD-B273) only adds an axe target-size check on S-R2's Similar ideas. |
| 4 | 1 → 1 | **Closed, not a product defect** (the product lead, 26 Nov; BLD-F110: a docs row only, no code change). The sticky phone bar's Back link covers the button at scrollY 170 (375 px wide), where J-TEAMUP/1–2's clicks (Team up, Send, Keep looking) left the page. The crew screen and the team-up sheet focus with `preventScroll: true`. |

BLD-D018 also gives the shared quiet link (`.link-quiet`, "Withdraw", BLD-D019) a 44 px hit area on touch. It reaches 10 px to each side and 20 px below, never above, so it cannot take a tap meant for "Requested".

## What axe does not check

axe tests only target size among the success criteria WCAG 2.2 adds at levels A and AA. The others need a person to check them, screen by screen, before the gate moves to 2.2:

- 2.4.11 Focus Not Obscured (Minimum). One case is already fixed: S-H2B's result line is scrolled into view after an answer (BLD-A228).
- 2.5.7 Dragging Movements.
- 3.2.6 Consistent Help.
- 3.3.7 Redundant Entry.
- 3.3.8 Accessible Authentication (Minimum).

## Turning the 2.2 gate on after launch

Items 1 and 3 are fixed, and items 2 and 4 come from where the tests leave the page, not from the app. So BLD-A229 is no longer only a matter of adding `"wcag22a"` and `"wcag22aa"` to the `withTags` list in `apps/web/e2e/helpers.ts`. As it stands, that pass would fail S-05 and S-H2 at the scroll positions the tests create. Run the 2.2 pass after `window.scrollTo(0, 0)`, then put the page back where it was, or run it at a position the app itself produces (lane D, BLD-D018). Keep the `target-size` rule on: it is what found the real overlaps in items 1 and 3. Land it on a branch whose CI is green, and only after the product lead agrees, since DEC-112 holds the gate at 2.1 AA for launch.
