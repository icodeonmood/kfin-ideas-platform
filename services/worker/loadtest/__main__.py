"""Load test (AT-B8-01, §9.3; BLD-A242): shares on the 1% Club's Share path and sign-ins at the launch rates, against
a running stack.

    uv run python -m loadtest --base-url http://<stack>:3000 --scale 0.1      # a 6-minute check
    uv run python -m loadtest --base-url http://<stack>:3000                  # the full hour

`--base-url` has no default. This machine's :3000 is refused (on the developer Mac it is the live demo, and a load
test never runs against the demo) unless `--not-the-demo` says that :3000 is a throwaway stack, as on a CI runner.

Targets (AT-B8-01): 150 shares an hour for one hour, plus 3,000 sign-ins spread over two hours (run here at the same
rate for the test's length); scan time at the 95th percentile 15 s or less; page load at the 95th percentile 2 s or
less (server response for the 1% Club's pages); error rate under 0.5%. `--scale` shortens the run and keeps the
rates: 0.1 is the same traffic per minute for six minutes.

People are synthetic employees from the HR directory (SYN-00018 upwards), signed in through the real OIDC flow
against the mock IdP, so the target is a dev-mode stack sized like UAT. Entra-backed UAT needs a sign-in route for
load accounts agreed with IT first (§9.1); there is no sign-in bypass. Their words are synthetic (the word list below).

Each share is one signed-in person on the Share path (J-SHARE), making the calls the browser makes, in its order:

    Tell it, S-04 and S-04B (app/share/compose.tsx, lib/compose/client.ts)
      GET   /share                                  the page
      POST  /api/drafts {channel, text, via}         the typed words, saved as the first message (Idempotency-Key)
      GET   /share/{id}                             the conversation, after Send on S-04
      GET   /api/drafts/{id}/stream?run={run}       the draft builds; read until `done`, then GET /api/drafts/{id}
                                                    once (a lost stream: GET /api/drafts/{id} every 3 s instead)
    Check it, S-05 (app/share/[id]/check/client.ts, check-it.tsx)
      GET   /share/{id}/check                       the page
      GET   /api/drafts/{id}, …/sorting, /api/config/uploads, then /api/ideas/{id}/similar, …/merge-request
      PATCH /api/drafts/{id}/sorting {confirm}      "Looks right" (L-SORT.rules/2); an empty field first takes the
                                                    first option of GET /api/config, as a person picks one
      GET   /api/drafts/{id}/send                   the declaration's version (L-SUBMIT.pre)
      PATCH /api/drafts/{id}/parts/{part} {value}   only when Send says the title or summary is missing
      POST  /api/drafts/{id}/submit                 Submit {declaration_version} (Idempotency-Key)
    S-06, the idea's page (app/ideas/[id])
      GET   /ideas/{ref}?from=share                 "Just shared"
      GET   /api/ideas/{ref}                        what the page shows, read again until it no longer says Checking

Scan time (the report's `scan` key, which `gonogo` reads) is send → sorted: from the Submit request until the idea
leaves `checking` for the review desk, that is until "Checked and matched" (L-SUBMIT.send/3: the last hidden-detail
pass and similar ideas, `submit.check`) is over. It counts as done only at `with_review_desk` (or `needs_you`, the
sharer's word for it with a question open); a share that ends in any other state or times out (`--scan-timeout`) is a
failed share, and its time still goes into the p95. A share that fails before Submit (the draft not built within
`--draft-timeout`, a refused step) is a failed share with no scan time. `draft` is create → built, for reading only.

The error rate is per operation (a sign-in, a page load, a share from its first save to sorted), not per HTTP
request. The report goes to `.data/loadtest/`: numbers, IDs and codes only, never words, names or emails (non-negotiable
3); so does every printed line.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import statistics
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http.cookiejar import CookieJar, DefaultCookiePolicy
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

TARGETS = {"scan_p95_s": 15.0, "page_p95_s": 2.0, "error_rate": 0.005}
# The 1% Club's pages a signed-in person opens: Home (`/` sends them to `/home`), the Wall, the Inbox, My ideas.
PAGES = ("/home", "/wall", "/inbox", "/my-ideas")
FLOW = "share"  # settings.flow: this report drives the Share path (BLD-A242), not the old canvas
CHECKING = "checking"
SORTED = frozenset({"with_review_desk", "needs_you"})  # "Checked and matched" is over (E-ENUMS.idea-status)
FIELDS = ("affects", "kind", "area", "brings")  # L-SORT.fields, as PATCH /api/drafts/{id}/sorting names them
POLL_S = 0.5  # between reads of the idea while it is Checking
RECOVER_S = 3.0  # a lost stream: the draft is read again this often (compose.tsx RECOVER_MS)
IDEMPOTENCY = "Idempotency-Key"  # lib/contracts/api.ts IDEMPOTENCY_HEADER
DEVICE = "X-Device-Id"  # lib/compose/client.ts: Tell it's calls carry the browser's opaque device id
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
REF_RE = re.compile(r"^IDEA-[0-9]{4}-[0-9]{6}$")
CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
WORDS = (
    "branch", "forms", "courier", "register", "mandate", "SIP", "NAV", "folio", "desk", "approval", "checklist",
    "scanner", "queue", "redemption", "nominee", "KYC", "batch", "report", "upload", "reconciliation",
)  # fmt: skip


def synthetic_text(rng: random.Random, n: int = 40) -> str:
    return "Load test (synthetic): " + " ".join(rng.choice(WORDS) for _ in range(n)) + "."


def synthetic_title(rng: random.Random) -> str:
    return f"Load test idea {rng.randrange(10**6)}: forms wait at the desk"


def code(value: object) -> str:
    """A server's code or state as the report may carry it: a short snake_case code, else `other`."""
    return value if isinstance(value, str) and CODE_RE.match(value) else "other"


def body_of(r: httpx.Response | None) -> dict[str, Any]:
    if r is None:
        return {}
    try:
        data = r.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def failed(step: str, r: httpx.Response | None) -> str:
    """`<step>_<status>[_<code>]` for a refused step, from the A-API error shape or the proxy's bare one."""
    if r is None:
        return f"{step}_no_answer"
    err = body_of(r).get("error")
    said = err.get("code") if isinstance(err, dict) else err
    return f"{step}_{r.status_code}" + (f"_{code(said)}" if said else "")


@dataclass
class Stats:
    timings: dict[str, list[float]] = field(default_factory=dict)
    requests: int = 0
    # per HTTP request and per failed share, for diagnosis
    errors: dict[str, int] = field(default_factory=dict)
    ops: dict[str, dict[str, int]] = field(default_factory=dict)
    notes: dict[str, int] = field(default_factory=dict)  # what people did that is not a failure

    def add(self, kind: str, seconds: float) -> None:
        self.timings.setdefault(kind, []).append(seconds)

    def error(self, kind: str) -> None:
        self.errors[kind] = self.errors.get(kind, 0) + 1

    def note(self, kind: str) -> None:
        self.notes[kind] = self.notes.get(kind, 0) + 1

    def op(self, kind: str, ok: bool) -> None:
        """One operation a person would notice: a sign-in, a page load, or a share through to sorted."""
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
        out: dict[str, Any] = {
            "requests": self.requests,
            "errors": dict(self.errors),
            "operations": self.ops,
            "notes": dict(self.notes),
        }
        for kind, vals in sorted(self.timings.items()):
            out[kind] = {
                "count": len(vals),
                "p50_s": self.p(vals, 50),
                "p95_s": self.p(vals, 95),
                "max_s": max(vals),
            }
        attempted = sum(o["attempted"] for o in self.ops.values())
        failures = sum(o["failed"] for o in self.ops.values())
        out["error_rate"] = failures / attempted if attempted else 0.0
        return out


@dataclass(frozen=True)
class Waits:
    scan_timeout: float = 120.0  # send → sorted
    draft_timeout: float = 120.0  # the draft building after the first save
    poll: float = POLL_S
    recover: float = RECOVER_S


class Session:
    """One person's browser: keeps cookies itself (session cookies are Secure, which httpx won't send to http), and
    its own opaque device id, as the browser keeps one (lib/compose/client.ts; random, never a person's detail)."""

    def __init__(self, client: httpx.AsyncClient, base: str, stats: Stats) -> None:
        self.client, self.base, self.stats = client, base, stats
        self.cookies: dict[str, str] = {}
        self.device = uuid.uuid4().hex

    def _headers(self, url: str, given: dict[str, str]) -> dict[str, str]:
        headers = dict(given)
        if self.cookies and url.startswith(self.base):
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        return headers

    def _keep_cookies(self, url: str, r: httpx.Response) -> None:
        if not url.startswith(self.base):
            return
        for header in r.headers.get_list("set-cookie"):
            jar: SimpleCookie = SimpleCookie()
            jar.load(header)
            for name, morsel in jar.items():
                if morsel.value and morsel.get("max-age") != "0":
                    self.cookies[name] = morsel.value
                else:
                    self.cookies.pop(name, None)

    async def request(self, method: str, path: str, kind: str, **kw: Any) -> httpx.Response | None:
        url = path if path.startswith("http") else self.base + path
        headers = self._headers(url, kw.pop("headers", {}))
        self.stats.requests += 1
        start = time.monotonic()
        try:
            r = await self.client.request(method, url, headers=headers, follow_redirects=False, **kw)
        except httpx.HTTPError:
            self.stats.error(kind)
            return None
        self.stats.add(kind, time.monotonic() - start)
        self._keep_cookies(url, r)
        if r.status_code >= 500:
            self.stats.error(kind)
        return r

    async def page(self, path: str) -> bool:
        """A page a person opens: one operation, server response time only."""
        r = await self.request("GET", path, "page")
        ok = r is not None and r.status_code < 400
        self.stats.op("page", ok)
        return ok

    async def until_done(self, path: str, timeout: float) -> str:
        """The draft's server-sent events, read as the browser's EventSource reads them, until `done`
        (A-API.draft-stream). `lost` when the stream ends or errs first, or drops; `timeout`; or `http_<status>`."""
        url = self.base + path
        headers = self._headers(url, {"Accept": "text/event-stream", DEVICE: self.device})
        self.stats.requests += 1

        async def read() -> str:
            async with self.client.stream("GET", url, headers=headers, follow_redirects=False) as r:
                self._keep_cookies(url, r)
                if r.status_code != 200:
                    if r.status_code >= 500:
                        self.stats.error("stream")
                    return f"http_{r.status_code}"
                async for line in r.aiter_lines():
                    if not line.startswith("event:"):
                        continue
                    name = line[len("event:") :].strip()
                    if name == "done":
                        return "done"
                    if name in ("end", "error"):
                        return "lost"
            return "lost"

        try:
            return await asyncio.wait_for(read(), timeout)
        except TimeoutError:
            return "timeout"
        except httpx.HTTPError:
            self.stats.error("stream")
            return "lost"

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
            await s.page(page)
    return s


async def draft_built(s: Session, draft_id: str, run_id: str | None, w: Waits) -> str:
    """S-04B: the draft builds from the words. With no run (too few words, or the assistant off) nothing builds."""
    if run_id is None:
        return "built"
    deadline = time.monotonic() + w.draft_timeout
    ended = await s.until_done(f"/api/drafts/{draft_id}/stream?run={quote(run_id, safe='')}", w.draft_timeout)
    if ended == "timeout":
        return "draft_timeout"
    path = f"/api/drafts/{draft_id}"
    if ended == "done":  # the browser reads the draft once more, and "Move to Review" turns on
        await s.request("GET", path, "api", headers={DEVICE: s.device})
        return "built"
    # Lost, or refused (an EventSource that fails is lost too): the browser reads the draft every 3 s until no run
    # is building (compose.tsx `lose`, `reread`).
    s.stats.error("draft_stream_lost" if ended == "lost" else f"draft_stream_{ended}")
    while True:
        r = await s.request("GET", path, "api", headers={DEVICE: s.device})
        if r is not None and r.status_code == 200:
            run = body_of(r).get("run")
            if not isinstance(run, dict) or run.get("state") != "running":
                return "built"
        if time.monotonic() + w.recover > deadline:
            return "draft_timeout"
        await asyncio.sleep(w.recover)


def first_picks(sorting: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """For each sorting field left empty, the first option a person sees (GET /api/config `sorting`)."""
    controls = config.get("controls") if isinstance(config.get("controls"), dict) else {}
    kinds = ((controls or {}).get("kind") or {}).get("options") or []
    choose: dict[str, Any] = {
        "affects": config.get("affects") or [],
        "area": config.get("areas") or [],
        "brings": [b for b in config.get("brings") or [] if b != "not_sure"],
        "kind": [k.get("value") for k in kinds if isinstance(k, dict) and k.get("value")] or ["problem"],
    }
    picks: dict[str, Any] = {}
    for f in FIELDS:
        now = sorting.get(f)
        if isinstance(now, dict) and now.get("value"):
            continue
        options = choose[f]
        if options:
            picks[f] = [options[0]] if f in ("affects", "brings") else options[0]
    return picks


async def checked_and_sent(
    s: Session, rng: random.Random, draft_id: str
) -> tuple[str, httpx.Response | None, float]:
    """S-05: the reads Check it makes as it opens, "Looks right" on the sorting, the Send part's last look, then
    Submit. Returns the Submit answer and the moment the Submit request left, or the refused step and None."""
    d = f"/api/drafts/{draft_id}"
    await s.page(f"/share/{draft_id}/check")
    draft, sorting_r, _ = await asyncio.gather(
        s.request("GET", d, "api"),
        s.request("GET", f"{d}/sorting", "api"),
        s.request("GET", "/api/config/uploads", "api"),
    )
    await asyncio.gather(  # similar ideas and the merge request, as Check it loads them
        s.request("GET", f"/api/ideas/{draft_id}/similar", "api"),
        s.request("GET", f"{d}/merge-request", "api"),
    )
    if draft is None or draft.status_code != 200:
        return failed("check_draft", draft), None, 0.0
    if sorting_r is None or sorting_r.status_code != 200:
        return failed("sorting", sorting_r), None, 0.0
    sorting = body_of(sorting_r)
    patch: dict[str, Any] = {"confirm": True}
    if sorting.get("complete") is not True:
        cfg = await s.request("GET", "/api/config", "api")
        config = body_of(cfg).get("sorting") if cfg is not None and cfg.status_code == 200 else None
        patch = {**first_picks(sorting, config if isinstance(config, dict) else {}), "confirm": True}
        s.stats.note("sorting_picked")
    confirmed = await s.request("PATCH", f"{d}/sorting", "api", json=patch)
    if confirmed is None or confirmed.status_code != 200 or body_of(confirmed).get("confirmed") is not True:
        return failed("sorting", confirmed), None, 0.0
    view_r = await s.request("GET", f"{d}/send", "api")
    if view_r is None or view_r.status_code != 200:
        return failed("send_view", view_r), None, 0.0
    view = body_of(view_r)
    declaration = view.get("declaration")
    version = declaration.get("version") if isinstance(declaration, dict) else None
    if not isinstance(version, str):
        return "send_view_no_declaration", None, 0.0
    for problem in view.get("problems") or []:
        if not isinstance(problem, dict) or problem.get("code") != "not_ready":
            continue
        part = problem.get("field")
        if part in ("title", "summary"):  # the person types it on part 1
            value = synthetic_title(rng) if part == "title" else synthetic_text(rng, 15)
            await s.request("PATCH", f"{d}/parts/{part}", "api", json={"value": value})
            s.stats.note(f"typed_{part}")
    start = time.monotonic()  # send → sorted starts with the Submit request
    sent = await s.request(
        "POST",
        f"{d}/submit",
        "api",
        json={"declaration_version": version},
        headers={IDEMPOTENCY: f"s05:{draft_id}:{uuid.uuid4()}"},
    )
    return "sent", sent, start


async def until_sorted(s: Session, ref: str, first: object, start: float, w: Waits) -> str:
    """S-06 says Checking until "Checked and matched" is over; the page is read again until it says otherwise."""
    state = first if isinstance(first, str) else CHECKING
    while state == CHECKING:
        if time.monotonic() - start >= w.scan_timeout:
            return "timeout"
        await asyncio.sleep(w.poll)
        r = await s.request("GET", f"/api/ideas/{ref}", "poll")
        idea = body_of(r).get("idea") if r is not None and r.status_code == 200 else None
        if isinstance(idea, dict) and isinstance(idea.get("status"), str):
            state = idea["status"]
    return state


async def share(s: Session, rng: random.Random, stats: Stats, w: Waits) -> str:
    """One share; returns `sorted`, or the code of the step that failed."""
    await s.page("/share")
    begun = time.monotonic()
    created = await s.request(
        "POST",
        "/api/drafts",
        "api",
        json={"channel": "web", "text": synthetic_text(rng), "via": "typed"},
        headers={IDEMPOTENCY: str(uuid.uuid4()), DEVICE: s.device},
    )
    if created is None or created.status_code != 201:
        return failed("create", created)
    made = body_of(created)
    draft = made.get("draft")
    draft_id = draft.get("id") if isinstance(draft, dict) else None
    if not isinstance(draft_id, str) or not UUID_RE.match(draft_id):
        return "create_no_draft"
    run_id = made.get("run_id")
    await s.page(f"/share/{draft_id}")
    built = await draft_built(s, draft_id, run_id if isinstance(run_id, str) else None, w)
    stats.add("draft", min(time.monotonic() - begun, w.draft_timeout))
    if built != "built":
        return built

    step, sent, start = await checked_and_sent(s, rng, draft_id)
    if step != "sent":
        return step
    if sent is None:
        return "submit_no_answer"
    if sent.status_code not in (200, 201):  # 200 is a repeated Submit's hand-over
        return failed("submit", sent)
    out = body_of(sent)
    ref = out.get("ref") or out.get("idea_id")
    if not isinstance(ref, str) or not REF_RE.match(ref):
        return "submit_no_ref"
    landed = asyncio.create_task(s.page(f"/ideas/{ref}?from=share"))
    state = await until_sorted(s, ref, out.get("status"), start, w)
    stats.add("scan", min(time.monotonic() - start, w.scan_timeout))
    await landed
    return "sorted" if state in SORTED else f"scan_{code(state)}"


async def submit_one(s: Session, rng: random.Random, stats: Stats, w: Waits) -> None:
    """One share: one operation, from the first save to sorted. A failed step fails it."""
    end = await share(s, rng, stats, w)
    stats.op("submission", end == "sorted")
    if end != "sorted":
        stats.error(end)


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


async def run(args: argparse.Namespace, transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    rng = random.Random(args.seed)  # noqa: S311 - synthetic traffic, not security
    stats = Stats()
    waits = Waits(scan_timeout=args.scan_timeout, draft_timeout=args.draft_timeout, poll=args.poll)
    length = 3600 * args.scale
    sign_in_rate = args.sign_ins / (args.sign_in_hours * 3600)  # per second
    submit_rate = args.submissions_per_hour / 3600
    people = [f"SYN-{n:05d}" for n in range(18, 18 + args.people)]
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
    # Each person's cookies live in their Session; the shared client must never keep any (B8 review).
    no_jar = httpx.Cookies(CookieJar(policy=DefaultCookiePolicy(allowed_domains=[])))
    async with httpx.AsyncClient(timeout=30, limits=limits, cookies=no_jar, transport=transport) as client:
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
            tasks.append(asyncio.create_task(at(t, submit_one(rng.choice(authors), rng, stats, waits))))
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
        "base_url": args.base_url, "scale": args.scale, "length_s": length, "flow": FLOW,
        "submissions_per_hour": args.submissions_per_hour, "sign_ins": args.sign_ins,
        "sign_in_hours": args.sign_in_hours, "scan_timeout_s": args.scan_timeout,
        "draft_timeout_s": args.draft_timeout, "poll_s": args.poll,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
    }  # fmt: skip
    return summary


def write_report(summary: dict[str, Any], out: Path) -> Path:
    """`report-<UTC time>.json` in `out`, the name `gonogo` looks for."""
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"report-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return path


def parse(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base-url", required=True, help="the stack to load; never the demo (see --not-the-demo)"
    )
    parser.add_argument(
        "--not-the-demo",
        action="store_true",
        help="allow a local :3000 target: only on a machine whose :3000 is a throwaway stack (a CI runner)",
    )
    parser.add_argument(
        "--scale", type=float, default=1.0, help="share of the hour to run; rates stay the same"
    )
    parser.add_argument("--submissions-per-hour", type=float, default=150, help="shares an hour")
    parser.add_argument("--sign-ins", type=int, default=3000)
    parser.add_argument("--sign-in-hours", type=float, default=2.0)
    parser.add_argument("--people", type=int, default=180, help="synthetic employees to sign in as")
    parser.add_argument("--authors", type=int, default=20, help="signed-in people who share")
    parser.add_argument("--scan-timeout", type=float, default=120.0, help="seconds from Submit to sorted")
    parser.add_argument(
        "--draft-timeout", type=float, default=120.0, help="seconds for the draft to build before Check it"
    )
    parser.add_argument("--poll", type=float, default=POLL_S, help="seconds between reads while Checking")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("../../.data/loadtest"))
    args = parser.parse_args(argv)
    if local_demo_port(args.base_url) and not args.not_the_demo:
        parser.error(
            "--base-url is this machine's :3000, where the dev stack and the demo run: a load test never runs "
            "against the demo (the product lead's rule). On a throwaway stack (a CI runner) add --not-the-demo."
        )
    return args


def local_demo_port(base_url: str) -> bool:
    """BLD-A242: whether `base_url` is this machine's port 3000, where the dev stack, and on the developer Mac the
    live demo, listen."""
    url = httpx.URL(base_url)
    port = url.port or (443 if url.scheme == "https" else 80)
    local = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}  # noqa: S104 - host names compared, never bound
    return url.host in local and port == 3000


def main(argv: Sequence[str] | None = None, transport: httpx.AsyncBaseTransport | None = None) -> int:
    args = parse(argv)
    summary = asyncio.run(run(args, transport))
    path = write_report(summary, args.out)
    for kind in ("scan", "draft", "page", "sign_in", "api", "poll"):
        if kind in summary:
            k = summary[kind]
            print(
                f"{kind:8} n={k['count']:5}  p50={k['p50_s']:.2f}s  p95={k['p95_s']:.2f}s  max={k['max_s']:.2f}s"
            )
    print(f"ops      {summary['operations']}")
    print(f"errors   {summary['errors']}  operation error rate={summary['error_rate']:.4f}")
    print(f"notes    {summary['notes']}")
    print(f"pass     {summary['pass']}")
    print(f"report   {path}")
    return 0 if all(summary["pass"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
