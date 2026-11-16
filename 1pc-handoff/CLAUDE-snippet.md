# Snippet for the repo's CLAUDE.md

Paste the block below into `CLAUDE.md` at the root of `kfin-ideas-platform` (adjust the path if the pack lives somewhere other than `docs/handoff/`). It tells every Claude Code session how to use the pack without re-reading it.

```markdown
## Design handoff (1% Club)

The design and behaviour spec lives in `docs/handoff/`. It is the source of truth for how the product looks, moves, reads and behaves.

- First time on this repo: read `docs/handoff/README.md` once, then `00-overview/PRODUCT.md`.
- Do not read the whole pack for a task. Find the module by ID in `docs/handoff/manifest.json` (it lists every module, its file, what it depends on and what uses it) and open only that file.
- IDs: `S-` screens, `C-` components, `F-` foundations, `J-` journeys, `L-` back-end logic, `E-`/`A-` contracts, `V-` validation, `P-` product. Anchors look like `S-R2.panel`; numbered lines like `S-R2.panel/3`.
- When asked to "apply D-00NN": open `docs/handoff/CHANGELOG.md`, read that entry only, open the files under its **Read** line at the named anchors, make the change, run the `V-ACC` tests it names. The module files already describe the new state; the entry's Old column tells you what to look for in the code.
- When two sources disagree: the latest CHANGELOG entry wins. After that, the module file wins on behaviour (rules, states, validation, data); the prototype board and its screenshot win on look (layout, spacing, colour, exact copy).
- The prototype boards are a design artefact. Take values, copy and behaviour from them; never copy their structure or their demo logic. Build from `01-foundations/tokens.json` and `reference/computed/components.md`.
- Exact wording for every screen and state is in `docs/handoff/reference/copy/<Board>.md`. Do not rewrite copy.
- Lines marked `OPEN:` or `NOT DRAWN:` give a default. Build the default; do not invent a different one. They are all listed in `00-overview/GAPS.md`.
- Keep `00-overview/REPO-MAPPING.md` current: when you build or move a screen, component or service, update its row.
- Everyone named on the boards is a fictional demo person. Never seed production with them.
- In code, reference the module ID in the test name and in the PR description (for example "Implements S-R2.panel, L-REVIEW.panel; tests V-ACC.review/1–6").
```

## Where to put the pack

Copy the whole `handoff/` folder to `docs/handoff/` in the repo and commit it. The `reference/shots/` folder is about 21 MB of JPEGs; if the repo should stay light, keep `reference/shots/` out of git and store it wherever design references already live (the repo has a `.design-refs/` folder), then fix the path in `README.md`.

## First prompt to give Claude Code

> Read `docs/handoff/README.md` and `docs/handoff/00-overview/PRODUCT.md`. Then do the first task in `docs/handoff/00-overview/REPO-MAPPING.md`: map every screen, component, logic module and contract in the pack to what already exists in this repo, mark each as "exists, matches", "exists, differs" or "missing", and list anything in the repo the pack does not describe. Do not change any code yet. Show me the filled-in mapping and a proposed build order.
