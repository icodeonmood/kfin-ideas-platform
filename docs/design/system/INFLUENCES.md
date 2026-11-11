# Where the ideas came from

Every borrowed idea, its source and licence. Nothing here changes the brand. The palette, type, mark and tagline come only from `docs/BRAND.md`. The full record, with commits and the safety scan of each repo, is `docs/design/SOURCES.md` in the app repo.

| What we took | From | Licence | Copied or referenced |
|---|---|---|---|
| A theme is only a set of custom-property overrides, so one component works on any surface: our White and Zed themes | Astryx (meta/astryx), theme architecture | MIT | Referenced (the idea; our values) |
| Named motion roles (press, state change, reveal) and the rule that reduced motion turns travel into a cross-fade of at most 200 ms on the `move` curve | Astryx, `packages/core/src/motion` | MIT | Referenced |
| Component anatomy and accessibility contracts for Banner, FieldStatus, EmptyState, Toast, AlertDialog, Stepper, Carousel and ProgressBar, behind our Status, PausedBanner, ConfirmInPlace, ChecksRunning, OnesStrip and StrengthMeter | Astryx components | MIT | Referenced |
| The expo-out curve `1.001 − 2^(−10t)`, our `ease-out` | Lenis (darkroomengineering/lenis) | MIT | Referenced (a curve, not code) |
| Optional smooth scrolling on brand pages | Lenis | MIT | Not used yet; waits for the product lead |
| Timeline choreography: labelled steps and offsets for the glow-up, the share moment and the launch | GSAP (greensock/GSAP) | GreenSock "no-charge" licence (not MIT, Apache, BSD or OFL) | Referenced only; rebuilt with the Web Animations API |

What we did **not** take: Astryx's themes (gothic, y2k and the rest are Meta's), its StyleX build, its CLI or its agent skills. None of its packages is installed: its install step writes agent instructions into the host project.
