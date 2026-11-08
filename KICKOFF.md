# Kickoff prompts for Claude Code

Open `~/rome/kfin-ideas-platform` in VS Code, start Claude Code in that folder, and paste the first prompt. Use the block prompts afterwards, one session (or one long session) per block.

---

## Prompt 1 — orientation, Garage inheritance and B1

```
You are building the KFintech Ideas Platform (The Garage · Ideas). Launch is Friday 20 November 2026, org-wide.

0. Run `git init`, then commit every file exactly as handed over, with the message "Handoff package v0.3", so later changes are traceable.
1. Read CLAUDE.md, then docs/DECISIONS.md, docs/DAY1_PLAN.md and docs/GARAGE_INHERITANCE.md in full.
   Skim docs/ARCHITECTURE.md end to end once, then read §2, §3.1–3.7, §4.1–4.4, §6, §7, §8 and §9 carefully.
2. Before writing code, reply with:
   - a one-paragraph summary of what you are building and for whom;
   - the ten non-negotiables in your own words;
   - anything in the docs that contradicts itself, with the reading you propose;
   - any question that blocks B1 (only blocking ones).
3. Do the Garage inheritance task exactly as docs/GARAGE_INHERITANCE.md describes. Read-only in ~/the-garage.
   Copy only the listed items into contracts/garage/ and docs/inherited/, with provenance headers.
   Write docs/inherited/REPORT.md and show me the summary table. If more than one candidate folder matches,
   list them and wait for me to choose.
4. Then build block B1 (Scaffold) from docs/DAY1_PLAN.md. Run its acceptance tests. Tick B1 in DAY1_PLAN.md,
   add a dated entry to docs/BUILD_LOG.md and record any defaults you chose in docs/DECISIONS.md.

Work in small commits. Synthetic data only. No real credentials. Stop and ask if a non-negotiable would bend.
```

---

## Block prompts

Use these as-is. Each assumes the previous block's tests pass.

**B2 — Identity and shell**
```
Build B2 from docs/DAY1_PLAN.md: mock OIDC sign-in (Entra-ready), users, contributor codes (HMAC), HR CSV import with
synthetic data, roles and the RBAC matrix from ARCHITECTURE §3.1 as a table-driven test, the app shell and navigation,
and axe checks in CI. Run the B2 acceptance tests, update DAY1_PLAN.md and BUILD_LOG.md.
```

**B3 — Canvas and attachments**
```
Build B3: quick capture and the full six-section canvas exactly as ARCHITECTURE §4.1 (questions, "why we ask" lines,
example links from guidance/canvas/ in the company repo), the deterministic strength meter from rules/thresholds.md,
drafts with autosave, the shared personal-data pattern rules (one source of test vectors used by both TypeScript and
Python), and day-one attachments (quarantine, virus scan, text-layer extraction, pattern check; images and scans held
as awaiting_check). Keyboard and screen-reader friendly. Run the B3 acceptance tests.
```

**B4 — Gateway and first agents**
```
Build B4: the LLM gateway (all nine steps in ARCHITECTURE §3.2), the pseudonym vault, restore-on-view, the llm_calls
log without text, kill switch ai.all with its automatic trigger, gatekeeper and canvas-assist using agents/<name>/
as drafted, scan status polling, and scan.async. LLM_MODE=fake for tests. Run make eval on the gatekeeper golden set
and the B4 acceptance tests. Tell me the eval numbers.
```

**B5 — Match**
```
Build B5: embeddings (BGE-M3, hash mode in tests), the search index from the company repo, router plans P2, P3 and P6,
the judge agent, match cards that obey the privacy rule in §4.2 step 7, and the choices (join, +1, adopt, mine is
different, withdraw), with the save transaction in §4.2 step 8. Run the judge golden set and the B5 acceptance tests.
```

**B6 — Review console**
```
Build B6: the review desk queue and item screen (§4.3), every action and what it writes, corrections, the core
committee's "Desk decisions" view and veto within 5 working days, review and veto timers from rules/sla.md with
rules/calendar.md, and communication module v1 (§3.7) for: submitted, quick-capture nudge, question, reviewed,
redirected, reconsidered, someone joined, adoption requested. Templates come from comms/templates/ in the company repo.
Run the B6 acceptance tests.
```

**B7 — Public pages**
```
Build B7: the public wall, My ideas, the idea page with timeline, the "Disagree with this?" link (creates a
disagreement item in the core committee's view) and the Garage showcase from solutions/. Respect visibility,
public_name_consent and restore-on-view. Run the B7 acceptance tests. Then prepare the UAT deployment notes.
```

**B8 — Hardening**
```
Run B8 with me: the pilot UAT checklist, golden sets, load test scripts (150 submissions an hour, 3,000 sign-ins),
restore drill steps, a kill-switch walkthrough and the launch-day runbook in ARCHITECTURE §9.5. Produce the
go/no-go report against the criteria in §9.3.
```
