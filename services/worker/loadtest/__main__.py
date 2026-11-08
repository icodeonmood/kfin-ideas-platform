"""Load test (AT-B8-01, §9.3): submissions and sign-ins at the launch rates, against a running stack.

    uv run python -m loadtest --base-url http://localhost:3000 --scale 0.1      # a 6-minute rehearsal
    uv run python -m loadtest --base-url http://<test Mac>:3000                     # the full hour

Targets (AT-B8-01): 150 submissions an hour for one hour, plus 3,000 sign-ins spread over two hours (run here at
the same rate for the test's length); scan time at the 95th percentile 15 s or less (submit → scan settled); page
load at the 95th percentile 2 s or less (server response for /, /wall, /my-ideas); error rate under 0.5%.
`--scale` shortens the run and keeps the rates: 0.1 is the same traffic per minute for six minutes.

People are synthetic employees from the HR directory (SYN-00018 upwards), signed in through the real OIDC flow
against the mock IdP, so the target is a dev-mode stack sized like UAT (the test Mac). Entra-backed UAT needs a
sign-in route for load accounts agreed with IT first (§9.1). The canvas text is synthetic.

A scan counts as done only when it reaches `done`; one left `waiting`, sent to `manual` or timed out is a failed
submission, and its time still goes into the p95. The error rate is per operation (a sign-in, a page load, a
submission from create to scan done), not per HTTP request. The report goes to `.data/loadtest/`, numbers only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http.cookiejar import CookieJar, DefaultCookiePolicy
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

import httpx

TARGETS = {"scan_p95_s": 15.0, "page_p95_s": 2.0, "error_rate": 0.005}
PAGES = ("/", "/wall", "/my-ideas")
WORDS = (
    "branch", "forms", "courier", "register", "mandate", "SIP", "NAV", "folio", "desk", "approval", "checklist",
    "scanner", "queue", "redemption", "nominee", "KYC", "batch", "report", "upload", "reconciliation",
)  # fmt: skip


def synthetic_text(rng: random.Random, n: int = 40) -> str:
    return "Load test (synthetic): " + " ".join(rng.choice(WORDS) for _ in range(n)) + "."


def canvas(rng: random.Random) -> dict[str, Any]:
    return {
        "kind": "problem",
        "one_line": f"Load test idea {rng.randrange(10**6)}: forms wait at the desk",
        "details": synthetic_text(rng),
        "who": {
            "segments": ["kfin_teams"],
            "frequency_or_reach": "daily",
            "today_alternative": "Manual checks",
        },
        "value": {"category": "cost_saving", "play": "process_improvement", "estimate": {}, "basis": "hunch"},
        "ecosystem": {"solved_elsewhere": "dont_know", "references": [], "our_advantage": ""},
        "solution": {},
        "visibility": "org",
        "declarations": {"no_personal_data": True, "own_work_or_credited": True, "ip_terms": True},
    }


@dataclass
class Stats:
    timings: dict[str, list[float]] = field(default_factory=dict)
    requests: int = 0
    errors: dict[str, int] = field(default_factory=dict)  # per HTTP request, for diagnosis
    ops: dict[str, dict[str, int]] = field(default_factory=dict)

    def add(self, kind: str, seconds: float) -> None:
        self.timings.setdefault(kind, []).append(seconds)

    def error(self, kind: str) -> None:
        self.errors[kind] = self.errors.get(kind, 0) + 1

    def op(self, kind: str, ok: bool) -> None:
        """One operation a person would notice: a sign-in, a page load, or a submission through to its scan."""
        counts = self.ops.setdefault(kind, {"attempted": 0, "failed": 0})
        counts["attempted"] += 1
        counts["failed"] += 0 if ok else 1

    @staticmethod
    def p(values: list[float], q: float) -> float | None:
        if not values:
            return None
        if len(values) == 1:
            return values[0]
        return statistics.quantiles(values, n=100, method="inclusive")[int(q) - 1]

    def summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {"requests": self.requests, "errors": dict(self.errors), "operations": self.ops}
        for kind, vals in sorted(self.timings.items()):
            out[kind] = {
                "count": len(vals),
                "p50_s": self.p(vals, 50),
                "p95_s": self.p(vals, 95),
                "max_s": max(vals),
            }
        attempted = sum(o["attempted"] for o in self.ops.values())
        failed = sum(o["failed"] for o in self.ops.values())
        out["error_rate"] = failed / attempted if attempted else 0.0
        return out


class Session:
    """One person's browser: keeps cookies itself (session cookies are Secure, which httpx won't send to http)."""

    def __init__(self, client: httpx.AsyncClient, base: str, stats: Stats) -> None:
        self.client, self.base, self.stats = client, base, stats
        self.cookies: dict[str, str] = {}

    async def request(self, method: str, path: str, kind: str, **kw: Any) -> httpx.Response | None:
        url = path if path.startswith("http") else self.base + path
        headers = dict(kw.pop("headers", {}))
        if self.cookies and url.startswith(self.base):
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        self.stats.requests += 1
        start = time.monotonic()
        try:
            r = await self.client.request(method, url, headers=headers, follow_redirects=False, **kw)
        except httpx.HTTPError:
            self.stats.error(kind)
            return None
        self.stats.add(kind, time.monotonic() - start)
        if url.startswith(self.base):
            for header in r.headers.get_list("set-cookie"):
                jar: SimpleCookie = SimpleCookie()
                jar.load(header)
                for name, morsel in jar.items():
                    if morsel.value and morsel.get("max-age") != "0":
                        self.cookies[name] = morsel.value
                    else:
                        self.cookies.pop(name, None)
        if r.status_code >= 500:
            self.stats.error(kind)
        return r

    async def sign_in(self, employee_id: str) -> bool:
        ok = await self._sign_in(employee_id)
        self.stats.op("sign_in", ok)
        return ok

    async def _sign_in(self, employee_id: str) -> bool:
        start = await self.request("GET", "/auth/login?next=/", "sign_in")
        if start is None or start.status_code not in (302, 307):
            self.stats.error("sign_in")
            return False
        try:
            form = await self.client.post(
                start.headers["location"],
                data={"username": employee_id, "claims": ""},
                follow_redirects=False,
            )
        except httpx.HTTPError:
            self.stats.error("sign_in")
            return False
        self.stats.requests += 1
        callback = await self.request("GET", form.headers.get("location", ""), "sign_in")
        if callback is None or callback.status_code not in (302, 303, 307):
            self.stats.error("sign_in")
            return False
        home = await self.request("GET", "/", "page")
        if (
            home is not None
            and home.status_code in (302, 307)
            and "privacy-notice" in home.headers.get("location", "")
        ):
            me = await self.request("GET", "/api/me", "api")
            notice = (me.json() if me is not None and me.status_code == 200 else {}).get(
                "privacy_notice"
            ) or {}
            version = notice.get("version")
            await self.request("POST", "/api/me/privacy-notice", "api", json={"version": version})
        return True


async def sign_in_and_browse(client: httpx.AsyncClient, base: str, stats: Stats, employee_id: str) -> Session:
    s = Session(client, base, stats)
    if await s.sign_in(employee_id):
        for page in PAGES:
            r = await s.request("GET", page, "page")
            stats.op("page", r is not None and r.status_code < 400)
    return s


async def submit_one(s: Session, rng: random.Random, stats: Stats, timeout: float) -> None:
    c = canvas(rng)
    created = await s.request("POST", "/api/submissions", "api", json={"mode": "full", "canvas": c})
    if created is None or created.status_code != 201:
        stats.op("submission", False)
        return
    draft = created.json()["id"]
    sent = await s.request("POST", f"/api/submissions/{draft}/submit", "api", json={"canvas": c})
    if sent is None or sent.status_code != 202:
        stats.op("submission", False)
        return
    start = time.monotonic()
    state = "timeout"
    while time.monotonic() - start < timeout:
        r = await s.request("GET", f"/api/submissions/{draft}/scan-status", "poll")
        state = r.json().get("state", "queued") if r is not None and r.status_code == 200 else "queued"
        if state not in ("queued", "running"):
            break
        await asyncio.sleep(0.5)
    # Done only when the scan finished; waiting (agent down, over time), manual (leak abort) or a timeout is a
    # failed submission, and its time still counts in the p95.
    stats.add("scan", min(time.monotonic() - start, timeout))
    stats.op("submission", state == "done")
    if state != "done":
        stats.error(f"scan_{state}")


def arrivals(rate_per_s: float, length_s: float, rng: random.Random) -> list[float]:
    """Poisson arrival times in [0, length)."""
    out: list[float] = []
    t = 0.0
    while rate_per_s > 0:
        t += rng.expovariate(rate_per_s)
        if t >= length_s:
            return out
        out.append(t)
    return out


async def run(args: argparse.Namespace) -> dict[str, Any]:
    rng = random.Random(args.seed)  # noqa: S311 - synthetic traffic, not security
    stats = Stats()
    length = 3600 * args.scale
    sign_in_rate = args.sign_ins / (args.sign_in_hours * 3600)  # per second
    submit_rate = args.submissions_per_hour / 3600
    people = [f"SYN-{n:05d}" for n in range(18, 18 + args.people)]
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
    # Each person's cookies live in their Session; the shared client must never keep any (B8 review).
    no_jar = httpx.Cookies(CookieJar(policy=DefaultCookiePolicy(allowed_domains=[])))
    async with httpx.AsyncClient(timeout=30, limits=limits, cookies=no_jar) as client:
        authors = [
            await sign_in_and_browse(client, args.base_url, stats, people[i]) for i in range(args.authors)
        ]
        authors = [a for a in authors if a.cookies]
        if not authors:
            raise SystemExit("no author could sign in; is the stack up and the mock IdP reachable?")
        begin = time.monotonic()
        tasks: list[asyncio.Task[Any]] = []

        async def at(t: float, coro: Any) -> None:
            await asyncio.sleep(max(0.0, begin + t - time.monotonic()))
            await coro

        for t in arrivals(sign_in_rate, length, rng):
            tasks.append(
                asyncio.create_task(
                    at(t, sign_in_and_browse(client, args.base_url, stats, rng.choice(people)))
                )
            )
        for t in arrivals(submit_rate, length, rng):
            tasks.append(
                asyncio.create_task(at(t, submit_one(rng.choice(authors), rng, stats, args.scan_timeout)))
            )
        await asyncio.gather(*tasks)
    summary = stats.summary()
    scan_p95 = (summary.get("scan") or {}).get("p95_s")
    page_p95 = (summary.get("page") or {}).get("p95_s")
    summary["targets"] = TARGETS
    summary["pass"] = {
        "scan_p95": scan_p95 is not None and scan_p95 <= TARGETS["scan_p95_s"],
        "page_p95": page_p95 is not None and page_p95 <= TARGETS["page_p95_s"],
        "error_rate": summary["error_rate"] < TARGETS["error_rate"],
        "launch_rate": args.submissions_per_hour >= 150 and args.sign_ins >= 3000,
    }
    summary["settings"] = {
        "base_url": args.base_url, "scale": args.scale, "length_s": length,
        "submissions_per_hour": args.submissions_per_hour, "sign_ins": args.sign_ins,
        "sign_in_hours": args.sign_in_hours, "at": datetime.now(UTC).isoformat(timespec="seconds"),
    }  # fmt: skip
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument(
        "--scale", type=float, default=1.0, help="share of the hour to run; rates stay the same"
    )
    parser.add_argument("--submissions-per-hour", type=float, default=150)
    parser.add_argument("--sign-ins", type=int, default=3000)
    parser.add_argument("--sign-in-hours", type=float, default=2.0)
    parser.add_argument("--people", type=int, default=180, help="synthetic employees to sign in as")
    parser.add_argument("--authors", type=int, default=20, help="signed-in people who submit")
    parser.add_argument("--scan-timeout", type=float, default=120.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("../../.data/loadtest"))
    args = parser.parse_args()
    summary = asyncio.run(run(args))
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"report-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for kind in ("scan", "page", "sign_in", "api", "poll"):
        if kind in summary:
            k = summary[kind]
            print(
                f"{kind:8} n={k['count']:5}  p50={k['p50_s']:.2f}s  p95={k['p95_s']:.2f}s  max={k['max_s']:.2f}s"
            )
    print(f"ops      {summary['operations']}")
    print(f"errors   {summary['errors']}  operation error rate={summary['error_rate']:.4f}")
    print(f"pass     {summary['pass']}")
    print(f"report   {path}")
    return 0 if all(summary["pass"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
