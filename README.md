# The Garage · Ideas — platform

KFintech's org-wide ideas platform, a sub-brand under The Garage. Launch: Friday 20 November 2026.

- Start here if you are Claude Code: [CLAUDE.md](CLAUDE.md), then [KICKOFF.md](KICKOFF.md).
- Start here if you are a person: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (the spec), [docs/DAY1_PLAN.md](docs/DAY1_PLAN.md) (what ships on day one), [docs/DECISIONS.md](docs/DECISIONS.md) (what is settled), [seed/README.md](seed/README.md) (content to sign off by 16 Nov).
- Diagrams: open [docs/diagrams/ideas-platform-diagrams.html](docs/diagrams/ideas-platform-diagrams.html) in a browser.

Internal. Synthetic data only in this repo.

## Run it locally

Needs Docker (Colima or Docker Desktop), `uv` and Node 22 or later. Everything runs on synthetic data.

| Command | Does |
|---|---|
| `make setup` | Install Python and Node dependencies and the Playwright browser |
| `make up` | Start Postgres, S3 store, ClamAV, mock OIDC, Mailpit, worker and web; waits until every health check passes |
| `make seed` | Create the local company repo in `.data/kfin-ideas`, validate it, index it |
| `make test` / `make e2e` / `make lint` / `make eval` | The gates every block must pass |
| `make killswitch NAME=submissions STATE=off REASON="…" ACTOR=REV-0001` | Flip a kill switch (audited) |

Web app: http://localhost:3000 · Mailpit: http://localhost:8025 · mock OIDC: http://localhost:8090

## Test Mac (full gates)

Day-to-day work happens on the development Mac. The full stack and every gate run on the test Mac (Apple silicon, 24 GB), which also takes the B8 load test (BLD-034).

1. `brew install gh && gh auth login`
2. `gh repo clone icodeonmood/kfin-ideas-platform ~/rome/kfin-ideas-platform && cd ~/rome/kfin-ideas-platform`
3. `scripts/setup-mac.sh --check` to see what is missing, then `scripts/setup-mac.sh` to set it up (installs missing Homebrew packages, creates a Colima VM sized to half the RAM, at most 12 GB; never resizes an existing one)
4. `make verify` runs up, seed, lint, test, e2e and eval, and stops at the first failure

After each push from the development Mac: `git pull && make verify`. `make down && colima stop` hands the VM's memory back when you are done.

