---
id: P-REPO
title: Where each module lands in the repo
rev: 1
status: pending
source: none
depends_on: []
last_delta: none
---

# Repo mapping (pending)

**Status: not filled in.** The repo at `~/rome/kfin-ideas-platform` could not be read when draft 0 was written: the folder-access request was not answered. Only its top-level folder names were visible:

`agents/`, `apps/`, `contracts/`, `db/`, `docs/`, `eval/`, `infra/`, `policy/`, `scripts/`, `seed/`, `services/`, plus `.design-refs/`.

Until this file is filled in, treat the pack as a design and behaviour spec and map it to the code yourself as the first task.

## `P-REPO.first-task` First task for Claude Code

Before building anything, fill in the tables below and commit this file:

1. Read the repo's own docs and decision log (`docs/`, any `DEC-` records, `CLAUDE.md`).
2. For every screen in `P-ROUTES.screens`: find the existing route and page component, if any. Record path, and one of: `exists, matches` / `exists, differs` / `missing`.
3. For every component in `02-components/INDEX.md`: find the existing component, if any, and record the same.
4. For every logic module in `05-logic/INDEX.md`: find the service, agent or policy that owns it (`services/`, `agents/`, `policy/`).
5. For every entity and endpoint in `06-contracts/`: find the schema or contract file (`contracts/`, `db/`) and list field-level differences.
6. List anything in the repo that this pack does not describe (so it can be kept, or raised).
7. Where the repo and this pack disagree on a product rule, the pack wins for look and behaviour; raise rule conflicts with the product owner rather than choosing. Known supersession: sorting is pre-filled and confirmed (see `P-DECISIONS.taken/2`), which replaces DEC-004 and DEC-094.

## `P-REPO.screens`

| ID | Repo route | Page component | State |
|---|---|---|---|
| (fill in) | | | |

## `P-REPO.components`

| ID | Repo component | State |
|---|---|---|
| (fill in) | | |

## `P-REPO.logic`

| ID | Service / agent / policy | State |
|---|---|---|
| (fill in) | | |

## `P-REPO.contracts`

| ID | Contract or schema file | Differences |
|---|---|---|
| (fill in) | | |

## `P-REPO.tokens`

Where the design tokens live in the repo, and whether `01-foundations/tokens.json` was imported as-is or mapped onto existing names.
