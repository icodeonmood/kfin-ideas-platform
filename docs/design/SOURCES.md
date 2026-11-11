# Design sources (lane D)

For: anyone checking where a design idea, value or file in the 1% Club redesign came from, and under what licence.

Rules (lane D brief): code, CSS, icons or fonts are copied only under MIT, Apache-2.0, BSD or OFL, with the notice kept. Anything else is reference only. Another company's identity (palette, logo, type, named themes) is never copied. The brand itself is fixed by `docs/BRAND.md` and is not up for borrowing.

## Sources

| Source | URL | Commit | Licence | Copied | Referenced only |
|---|---|---|---|---|---|
| Astryx (Meta's design system) | https://github.com/meta/astryx | `63bbda14b3d6ab8085b4ca791fe1c19b8fa25162` | MIT, © 2026 Meta Platforms | Nothing yet | Theme-as-custom-properties architecture; motion roles (named durations and curves) and the Reduce Motion cross-fade rule (≤ 200 ms on `curves.move`); component anatomy and a11y contracts for Banner, EmptyState, FieldStatus, Toast, Dialog/AlertDialog, Stepper, Carousel, ProgressBar, SegmentedControl, StatusDot |
| Lenis (smooth scroll) | https://github.com/darkroomengineering/lenis | `e01eefb1f55cd08bc051521d74f5f8182b71ee9d` | MIT, © 2024 darkroom.engineering | Nothing yet | Its expo-out scroll curve `1.001 − 2^(−10t)`; candidate dependency for brand pages only (needs the product lead's yes and a DEC row) |
| GSAP (GreenSock) | https://github.com/greensock/GSAP | `5e6c35ff8eedea12d4f229129def635277d8b0f2` | GreenSock "Standard no-charge licence" (gsap.com/standard-license). Not MIT, Apache, BSD or OFL | Nothing; never | Timeline thinking (sequenced, labelled choreography) for the glow-up and the launch reveal, rebuilt with CSS and the Web Animations API |
| **Vengeance UI: REJECTED, malware** | https://github.com/Ashutoshx7/VengeanceUI (site vengenceui.com) | `6beca5f9317aa8842640d267abe95f6e2ecc5343` | MIT on paper | Nothing; never | Nothing. `postcss.config.mjs` hides 6,055 characters of obfuscated JavaScript after ~730 spaces on its last line. It runs on `npm run dev` or `next build`, grabs `require`, `module` and file paths, and executes a decoded payload through `Function`. Found 11 Nov 2026; never run; clone deleted; defanged evidence in `.design-refs/_quarantine/vengeanceui/MALWARE-EVIDENCE.txt` (sha256 `3522bf85…1ff2`). The "liquid glass" look the product lead pointed to is rebuilt from first principles (SVG displacement and backdrop filters), with no code from this repo |

When something is copied, add a row below with the file, the target path in this repo and the notice kept.

### Copied files

| From (source, path) | To (this repo) | Licence notice kept where |
|---|---|---|
| — | — | — |

## How the references were fetched and checked (11 Nov 2026)

They were cloned shallow over HTTPS into `.design-refs/<name>` at the project root. `.design-refs/` is in `.git/info/exclude`, so it is never committed. The clone ran with hooks off (`core.hooksPath=/dev/null`), no submodules, no LFS smudge, `core.symlinks=false` and `protocol.file.allow=never`. Nothing from the clones has been installed, built or run.

**Agent and IDE files quarantined.** Astryx ships instructions for coding agents: `CLAUDE.md`, `AGENTS.md` (three copies), `.claude/` (two skills, two commands), `.claude-plugin/` and `.agents/` marketplaces, a Claude/Codex plugin with a `SKILL.md`, and `.husky/` git hooks. Lenis ships `.vscode/`. Claude Code can load nested `CLAUDE.md` files and directory-scoped skills, so all of these were moved to `.design-refs/_quarantine/` with neutral names (`dot-claude/`, `*.md.txt`). No loader can discover them there. They were read as data: nothing in them is hostile. They tell an agent to read `AGENTS.md` and to run the `astryx` CLI.

**Static scan** (a script outside the clones, run against them as arguments):

| Check | Astryx | Lenis | GSAP |
|---|---|---|---|
| Install-time scripts | `postinstall` in `@astryxdesign/core` and `@astryxdesign/cli`: they only print a nudge to run `astryx init`, which writes agent docs into the host project. The sandbox app's `postinstall` runs `astryx init --features agents`. **Never install these packages in this repo.** | None | None |
| Native binaries | None (only executable `.mjs` and `.sh` dev scripts) | None | None |
| `child_process` / `eval` / `new Function` | `child_process` only in its own test and eval tooling; no `eval` | None | None (`.exec(` hits are RegExp) |
| Pipe-to-shell, miners, credential paths | None | None | None |
| Hidden bidi or zero-width characters | None | None | None |
| Very long lines | Docs strings and an HTML entity table | None | An emoji regex and the dev-tools stylesheet string |
| Prompt-injection phrasing in docs | None | None | None |
| Outbound hosts in source | Docs, CDNs, placeholder images, npm | Docs links | gsap.com, greensock.com, codepen |

**Hardened checks (added 11 Nov after Vengeance UI):** a run of 200+ spaces or tabs followed by code on the same line (code files), every build-time config (`postcss`, `tailwind`, `next`, `vite`, `eslint`, `babel`…) listed with its longest line, and obfuscation markers (`String.fromCharCode(127)`, `_$_xxxx=(function`, `global[_$_`). Astryx, Lenis and GSAP pass all three.

**Verdict:** safe to read as reference. Do not install Astryx (its install path writes agent files into the project), and do not run any of the three repos' scripts. If Lenis is approved as a dependency, add it from npm at an exact pinned version with `--ignore-scripts`, and check the published tarball against this commit's `packages/core/src`.
