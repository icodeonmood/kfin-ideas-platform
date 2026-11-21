"""Find your crew (L-CREW/1–10, C-CREW-DECK data, A-API.team-up `GET /crew` and the passes).

The deck is worked out on read from stored facts (ideas, crew_members, teamup_requests, similar_links, crew_passes),
so it is current whenever the page loads. Cards follow the preview's rules (DEC-104, non-negotiable 7, BLD-F042):
the title masked, one checked sentence of the short summary, the sharer's "Who would help" answer checked the same
way (else their picks), the similar-match reason, which L-SIMILAR stores masked, and people through
`similar.preview.person_refs`, so a hidden or departed person is "A colleague". Nothing here opens anyone's sealed
words, and nothing is logged.

Entry points (each takes the `users.id` of the person asking):

    deck(conn, user_id, filters=None, *, limit=None, now=None, include_crews=True) -> dict   # GET /crew
    home(conn, user_id, limit=3, now=None) -> {"total": int, "top": [CrewCard]}               # A-API.home crew
    pass_idea(conn, user_id, idea_ref) -> dict                                              # POST /crew/pass
    undo_last(conn, user_id, now=None) -> dict                                              # POST /crew/pass/undo
    reset(conn, user_id) -> dict                                                            # POST /crew/pass/reset
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.db import Conn
from crew.store import Refused, Viewer, day_label, viewer
from crew.store import now as _now
from onepc import enums
from pii.patterns import scan
from similar.preview import HIDDEN_NAME, SUMMARY_PENDING, checked_sentence, mask_text, person_refs

# L-CREW/2: the one reason a card is shown, strongest first (E-ENUMS.match `crew_reason`).
REASONS: tuple[str, ...] = tuple(enums.values("crew_reason"))
# L-CREW/1 with L-TEAMUP/1: shared ideas still open to a crew. Closed ones (not picked, not now, withdrawn, merged)
# cannot be joined; shipped ones have nothing left to help with (BLD-F030).
OPEN_STATUSES: tuple[str, ...] = ("checking", "with_review_desk", "needs_you", "picked", "being_built")
FACES = 3  # crew faces on a card (C-CREW-DECK.card: "RN AS PK", "Ravi Nair and 3 others on it")

TEAM_SIZES: tuple[tuple[str, str], ...] = (
    ("lead_only", "Just the lead"),
    ("two_to_three", "2 to 3 people"),
    ("four_plus", "4 or more"),
)
# L-CREW/5, in the filter panel's order (board Crew, "Filters open").
FILTERS: tuple[tuple[str, str], ...] = (
    ("location", "Location"),
    ("category", "Category"),
    ("status", "Idea status"),
    ("team_size", "Team size"),
    ("looking_for", "Looking for"),
)
FILTER_KEYS = frozenset(k for k, _ in FILTERS)
# The board's Crew deck shows a just-shared idea (`checking`) as "Shared" (BLD-F030); every other status keeps its
# E-ENUMS label.
STATUS_LABELS: dict[str, str] = {**enums.labels("idea_status"), "checking": "Shared"}
TEAMED_LINK = "/my-ideas?list=teamed"  # L-CREW/9: "All your crews in My ideas" → My ideas, Teamed up


# ---------------------------------------------------------------------------------------------------------------
# Pure rules (unit-tested without a database)
# ---------------------------------------------------------------------------------------------------------------
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def first_sentence(text: str | None, limit: int = 160) -> str:
    """One sentence for a card ("the problem, in their words", L-CREW/4), cut at a word with "…" if long."""
    t = " ".join((text or "").split())
    if not t:
        return ""
    s = _SENTENCE_END.split(t, maxsplit=1)[0]
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return s


def looking_for(picks: Sequence[str], text: str | None) -> str | None:
    """ "They're looking for" (L-CREW/4): the sharer's own "Who would help" answer, else their picks from the list.
    Empty stays empty: there is no AI in this path to write one from the idea (BLD-F031). `text` is the answer as
    `similar.preview.checked_sentence` returns it (masked and checked, BLD-F042); one that still trips a
    personal-data pattern is never shown, and the picks stand in for it."""
    typed = (text or "").strip()
    if typed and not scan(typed):
        return first_sentence(typed)
    named = [p.strip() for p in picks if p and p.strip()]
    if not named:
        return None
    return ", ".join([named[0], *(p[:1].lower() + p[1:] for p in named[1:])])


def team_size(count: int) -> str:
    """L-CREW/5 Team size: Just the lead; 2 to 3 people; 4 or more (the lead counts, L-TEAMUP/12)."""
    if count <= 1:
        return "lead_only"
    return "two_to_three" if count <= 3 else "four_plus"


_STOP = frozenset(
    {"someone", "anyone", "people", "person", "from", "with", "team", "teams", "staff", "help", "helps", "knows",
     "that", "this", "good", "and", "the", "who", "works", "work", "they", "their"}
)  # fmt: skip


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 4 and w not in _STOP]


def touches(picks: Sequence[str], area: str | None) -> bool:
    """ "Touches their work" (L-CREW/2): the sharer asked for help from the person's own line of work. The area's
    first telling word ("investor" in Investor service, "technology") meets a word of a "Who would help" pick,
    either way round as a prefix ("tech" and "technology", "operations")."""
    head = _words(area or "")
    if not head:
        return False
    key = head[0]
    return any(w.startswith(key) or key.startswith(w) for p in picks for w in _words(p))


_STRENGTH_PREFIX = re.compile(
    r"^\s*(?:" + "|".join(re.escape(v) for v in enums.labels("match_strength").values()) + r")\s*:\s*", re.I
)


def close_reason(stored: str | None, forward: bool, mine_shared_at: dt.datetime, current: dt.datetime) -> str:
    """The card line for "close to an idea of theirs" (L-CREW/2: "Same R07 SMS as your idea from Saturday").

    L-SIMILAR writes each match's reason for the sharer of the idea it was found for, so it reads right to this
    person only when the match was found for their idea (`forward`). Otherwise, or with no reason, the line names
    their idea and its day (BLD-F032)."""
    day = day_label(mine_shared_at, current)
    text = _STRENGTH_PREFIX.sub("", stored or "").strip().rstrip(".")
    if not forward or not text:
        return f"Close to your idea from {day}"
    text = text[0].upper() + text[1:]
    if text.lower().startswith("same "):
        return f"{text} as your idea from {day}"
    return f"{text}, like your idea from {day}"


def touches_reason(area: str) -> str:
    return f"They need someone in {area}"


def area_reason(area: str) -> str:
    return f"Your area, {area}"


def office_reason(city: str) -> str:
    return f"Same office as you, {city}"


def hue(ref: str) -> int:
    """C-CREW-DECK's two light washes, fixed per idea so a card keeps its colour when filters change."""
    digits = re.sub(r"[^0-9]", "", ref)
    return 1 + (int(digits[-1]) % 2 if digits else 0)


# ---------------------------------------------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Card:
    uuid: str
    ref: str
    title: str
    status: str
    area: str
    city: str
    shared_at: dt.datetime
    lead: dict[str, Any]  # E-ENTITIES PersonRef, from similar.preview.person_refs (BLD-F042)
    faces: tuple[dict[str, Any], ...]
    crew_count: int
    in_their_words: str
    looking_for: str | None
    picks: tuple[str, ...]
    reason_kind: str
    reason: str
    strength: tuple[int, int, int, int]  # reason, close before related, the match's own order, its idea's day
    # DEC-126 (BLD-F094): the person's own request still waiting on this idea, as (request id, "teamup" | "merge"),
    # and when they asked; None when they have not asked.
    request: tuple[str, str] | None = None
    requested_at: dt.datetime | None = None

    def facets(self) -> dict[str, tuple[str, ...]]:
        return {
            "location": (self.city,) if self.city else (),
            "category": (self.area,) if self.area else (),
            "status": (self.status,),
            "team_size": (team_size(self.crew_count),),
            "looking_for": self.picks,
        }

    def as_json(self) -> dict[str, Any]:
        """E-ENTITIES CrewCard (IdeaPreview + reason_kind, reason). `compare` is for reviewers only, never here."""
        out: dict[str, Any] = {
            "id": self.ref,
            "title": self.title,
            "status": self.status,
            "area": self.area,
            "city": self.city,
            "shared_at": self.shared_at.isoformat(),
            "lead": dict(self.lead),
            "crew_faces": [dict(p) for p in self.faces],
            "crew_count": self.crew_count,
            "in_their_words": self.in_their_words,
            "hue": hue(self.ref),
            "reason_kind": self.reason_kind,
            "reason": self.reason,
        }
        if self.looking_for:
            out["looking_for"] = self.looking_for
        if self.request is not None:
            # DEC-126: "Requested" with "Withdraw" (`DELETE /team-up/:id` withdraws either kind). The id is the
            # viewer's own request's; nothing else about it, and never its note (BLD-F094).
            out["request"] = {"id": self.request[0], "kind": self.request[1]}
        return out


def order_key(c: Card) -> tuple[int, int, int, int, int, float]:
    """L-CREW/3 under DEC-126 (BLD-F094): by the reason's strength, then the most recently shared first. An idea the
    person has asked to join comes after every other card, the oldest request first, so the newest is last."""
    if c.requested_at is not None:
        return (1, 0, 0, 0, 0, c.requested_at.timestamp())
    return (0, *c.strength, -c.shared_at.timestamp())


def limited(shown: Sequence[Card], limit: int | None) -> list[Card]:
    """A short read of the deck (`limit`; Home's top three, S-03), lane F's reading of DEC-126 (2) (BLD-F094; amended
    by BLD-F096).

    Requested cards sort last, so a person with `limit` or more other cards would lose the one they just asked about
    from Home after a reload. So when the deck is longer than `limit` and holds a requested card, the read is up to
    `limit - 1` other cards in deck order, then the latest requested cards in deck order to fill the read to `limit`
    (requested cards are oldest request first, so the most recently requested card is last). The read always holds
    `min(limit, len(shown))` cards. A deck that fits in `limit` comes whole, in order, as without a limit."""
    if not limit or len(shown) <= limit:
        return list(shown)
    asked = [c for c in shown if c.request is not None]
    if not asked:
        return list(shown[:limit])
    others = [c for c in shown if c.request is None][: limit - 1]
    # at least 1, and never more than `asked` holds, since the deck is longer than `limit`
    room = limit - len(others)
    return [*others, *asked[-room:]]


@dataclass(frozen=True)
class _Link:
    strength: str
    forward: bool
    rank: int
    reason: str
    mine_shared_at: dt.datetime

    def key(self) -> tuple[int, int, int, float]:
        return (0 if self.strength == "close" else 1, 0 if self.forward else 1, self.rank,
                -self.mine_shared_at.timestamp())  # fmt: skip


def _links(conn: Conn, v: Viewer) -> dict[str, _Link]:
    """The best similar-match link from each other idea to one of this person's shared ideas (L-SIMILAR/5–6: found
    for theirs, or found later for a newer idea that matched theirs)."""
    if not v.code:
        return {}
    best: dict[str, _Link] = {}
    for r in conn.execute(
        "SELECT s.idea_uuid::text AS a, s.other_idea_uuid::text AS b, s.strength, s.reason, s.rank, "
        "mine.id::text AS mine, mine.shared_at AS mine_shared_at "
        "FROM ideas mine JOIN similar_links s ON mine.id IN (s.idea_uuid, s.other_idea_uuid) "
        "WHERE mine.contributor_code = %s AND mine.shared_at IS NOT NULL "
        "AND mine.status NOT IN ('draft', 'withdrawn', 'merged')",
        (v.code,),
    ).fetchall():
        forward = r["a"] == r["mine"]
        other = r["b"] if forward else r["a"]
        link = _Link(str(r["strength"]), forward, int(r["rank"]), str(r["reason"] or ""), r["mine_shared_at"])
        if other not in best or link.key() < best[other].key():
            best[other] = link
    return best


_ELIGIBLE = """
SELECT i.id::text AS uuid, i.idea_id, i.title, i.status, i.area, i.city, i.shared_at, i.summary,
       i.helper_picks, i.helper_text, i.contributor_code,
       coalesce(c.codes, ARRAY[]::text[]) AS crew_codes, c.lead_code,
       rq.id AS request_id, rq.kind AS request_kind, rq.sent_at AS requested_at
FROM ideas i
LEFT JOIN LATERAL (
  SELECT array_agg(cm.contributor_code ORDER BY (cm.role = 'lead') DESC, cm.joined_at, cm.id) AS codes,
         max(cm.contributor_code) FILTER (WHERE cm.role = 'lead') AS lead_code
  FROM crew_members cm WHERE cm.idea_uuid = i.id AND cm.left_at IS NULL
) c ON true
LEFT JOIN LATERAL (
  SELECT q.id::text AS id, q.kind, q.sent_at FROM (
    SELECT t.id, 'teamup'::text AS kind, t.sent_at FROM teamup_requests t
    WHERE t.idea_uuid = i.id AND t.from_code = %(code)s AND t.state = 'sent'
    UNION ALL
    SELECT mr.id, 'merge'::text, mr.sent_at FROM merge_requests mr
    WHERE mr.other_idea_uuid = i.id AND mr.from_code = %(code)s AND mr.state = 'waiting'
  ) q ORDER BY q.sent_at DESC, q.id DESC LIMIT 1
) rq ON true
WHERE i.status = ANY(%(open)s) AND i.shared_at IS NOT NULL AND i.idea_id IS NOT NULL
  AND i.contributor_code IS DISTINCT FROM %(code)s
  AND NOT EXISTS (SELECT 1 FROM crew_members m
                  WHERE m.idea_uuid = i.id AND m.contributor_code = %(code)s AND m.left_at IS NULL)
  AND NOT EXISTS (SELECT 1 FROM teamup_requests t
                  WHERE t.idea_uuid = i.id AND t.from_code = %(code)s AND t.state = 'declined')
  AND NOT EXISTS (SELECT 1 FROM merge_requests mr
                  WHERE mr.other_idea_uuid = i.id AND mr.from_code = %(code)s AND mr.state = 'declined')
  AND NOT EXISTS (SELECT 1 FROM crew_passes p
                  WHERE p.user_id = %(uid)s AND p.idea_uuid = i.id AND p.undone_at IS NULL)
"""


def cards_for(conn: Conn, v: Viewer, current: dt.datetime) -> list[Card]:
    """The whole deck for this person, in order, before filters (L-CREW/1–4).

    L-CREW/1 under DEC-126 (BLD-F094): shared ideas still open to a crew that the person is not on, was not declined
    on (a team-up request, or a draft's merge request, BLD-F038) and has not passed. An idea they have asked to join
    and are still waiting on stays, as "Requested" with its request (`Card.request`), and sorts last (`order_key`);
    a withdrawn request is as if never asked. Each card needs one of the four reasons of L-CREW/2; an idea with none
    is not shown."""
    rows = conn.execute(_ELIGIBLE, {"open": list(OPEN_STATUSES), "code": v.code, "uid": v.user_id}).fetchall()
    links = _links(conn, v)
    plans: list[tuple[dict[str, Any], str, str, tuple[int, int, int, int], list[str], str]] = []
    for r in rows:
        picks = [str(p) for p in (r["helper_picks"] or [])]
        area, city = str(r["area"] or ""), str(r["city"] or "")
        link = links.get(r["uuid"])
        if link is not None:
            kind = "close_to_yours"
            reason = close_reason(link.reason, link.forward, link.mine_shared_at, current)
            sub = (0 if link.strength == "close" else 1, link.rank, 0)
        elif v.area and touches(picks, v.area):
            kind, reason, sub = "touches_your_work", touches_reason(v.area), (0, 0, 0)
        elif v.area and area and area.casefold() == v.area.casefold():
            kind, reason, sub = "same_area", area_reason(area), (0, 0, 0)
        elif v.city and city and city.casefold() == v.city.casefold():
            kind, reason, sub = "same_office", office_reason(city), (0, 0, 0)
        else:
            continue
        codes = [str(c) for c in r["crew_codes"]] or [str(r["contributor_code"])]
        lead = str(r["lead_code"] or r["contributor_code"])
        if lead in codes:
            codes.remove(lead)
        plans.append((dict(r), kind, reason, (REASONS.index(kind), *sub), [lead, *codes], area))
    # The card follows the preview's rules (BLD-F042, DEC-104): a person who hid their name from the Wall, or has
    # left, is "A colleague" with no user id; "the problem, in their words" and a typed "Who would help" answer are
    # one masked sentence that passes the tag, pattern and name checks.
    people = person_refs(conn, sorted({c for p in plans for c in p[4]}), names_always=False)
    cards: list[Card] = []
    for r, kind, reason, strength, codes, area in plans:
        crew = [people[c] for c in codes]
        wanted = tuple(str(p) for p in (r["helper_picks"] or []))
        asked = (str(r["request_id"]), str(r["request_kind"])) if r["request_id"] else None
        cards.append(
            Card(
                r["uuid"], str(r["idea_id"]), mask_text(r["title"]).strip() or str(r["idea_id"]), str(r["status"]),
                area, str(r["city"] or ""), r["shared_at"], crew[0], tuple(crew[:FACES]), len(codes),
                checked_sentence(conn, r["summary"]) or SUMMARY_PENDING,
                looking_for(wanted, checked_sentence(conn, r["helper_text"])), wanted, kind, reason, strength,
                asked, r["requested_at"] if asked else None,
            )
        )  # fmt: skip
    return sorted(cards, key=order_key)


# ---------------------------------------------------------------------------------------------------------------
# Filters (L-CREW/5)
# ---------------------------------------------------------------------------------------------------------------
Active = dict[str, list[str]]


def normalise(filters: Mapping[str, Iterable[str]] | None) -> Active:
    """Known filter keys only, values trimmed and de-duplicated in the order given. Unknown statuses and team sizes
    are dropped; an unknown city, area or pick is kept so its chip can still be removed (it counts 0)."""
    out: Active = {}
    sizes = {k for k, _ in TEAM_SIZES}
    for key, _ in FILTERS:
        seen: list[str] = []
        for raw in (filters or {}).get(key, ()) or ():
            val = str(raw).strip()[:120]
            if not val or val in seen:
                continue
            if key == "status" and val not in enums.IDEA_STATUS:
                continue
            if key == "team_size" and val not in sizes:
                continue
            seen.append(val)
        if seen:
            out[key] = seen
    return out


def _matches(c: Card, active: Active, skip: str | None = None) -> bool:
    f = c.facets()
    return all(set(f[k]) & set(vals) for k, vals in active.items() if k != skip and vals)


def option_label(key: str, value: str) -> str:
    if key == "status":
        return STATUS_LABELS.get(value, value)
    if key == "team_size":
        return dict(TEAM_SIZES).get(value, value)
    return value


def _options(cards: Sequence[Card], key: str, active: Active) -> list[str]:
    if key == "team_size":
        return [k for k, _ in TEAM_SIZES]
    present: list[str] = []
    for c in cards:
        for val in c.facets()[key]:
            if val not in present:
                present.append(val)
    if key == "status":
        present = [s for s in enums.IDEA_STATUS if s in present]
    elif key == "looking_for":
        present.sort(key=str.casefold)
    return present + [v for v in active.get(key, []) if v not in present]


def facet_groups(cards: Sequence[Card], active: Active) -> list[dict[str, Any]]:
    """Every filter with its options and live counts (L-CREW/5). An option's count is how many cards it would show
    with the other filters as they are (so Hyderabad still says 2 while Hyderabad is on). Location and Category
    follow the deck's order, Idea status the status order, Looking for the alphabet."""
    groups: list[dict[str, Any]] = []
    for key, label in FILTERS:
        values = _options(cards, key, active)
        tally = dict.fromkeys(values, 0)
        for c in cards:
            if _matches(c, active, skip=key):
                for val in c.facets()[key]:
                    if val in tally:
                        tally[val] += 1
        on = set(active.get(key, []))
        groups.append({
            "key": key,
            "label": label,
            "options": [{"value": val, "label": option_label(key, val), "count": tally[val], "active": val in on}
                        for val in values],
        })  # fmt: skip
    return groups


def chips(active: Active) -> list[dict[str, str]]:
    """The active filters, echoed for the chips above the deck."""
    return [
        {"key": k, "value": val, "label": option_label(k, val)}
        for k, _ in FILTERS
        for val in active.get(k, [])
    ]


# ---------------------------------------------------------------------------------------------------------------
# The deck, Home, "Your crews" and the person's tallies
# ---------------------------------------------------------------------------------------------------------------
def tallies(conn: Conn, v: Viewer) -> dict[str, Any]:
    """`{ joined, pending, passed }` (A-API.team-up), plus `asked` for the end of the deck (L-CREW/7: "You asked to
    team up on 1 idea"; every idea asked about, withdrawn requests aside) and the last pass, for "Undo last pass".
    A draft's merge request asks to join too (BLD-F038)."""
    row = conn.execute(
        "SELECT "
        " (SELECT count(*) FROM crew_members m WHERE m.contributor_code = %(code)s AND m.left_at IS NULL "
        "    AND m.role = 'crew') AS joined, "
        " (SELECT count(*) FROM teamup_requests t WHERE t.from_code = %(code)s AND t.state = 'sent') "
        "  + (SELECT count(*) FROM merge_requests mr WHERE mr.from_code = %(code)s AND mr.state = 'waiting') "
        "  AS pending, "
        " (SELECT count(DISTINCT a.idea_uuid) FROM ("
        "    SELECT t.idea_uuid FROM teamup_requests t WHERE t.from_code = %(code)s AND t.state <> 'withdrawn' "
        "    UNION ALL SELECT mr.other_idea_uuid FROM merge_requests mr WHERE mr.from_code = %(code)s "
        "      AND mr.state NOT IN ('withdrawn', 'none')) a) AS asked, "
        " (SELECT count(*) FROM crew_passes p WHERE p.user_id = %(uid)s AND p.undone_at IS NULL) AS passed, "
        " (SELECT i.idea_id FROM crew_passes p JOIN ideas i ON i.id = p.idea_uuid "
        "    WHERE p.user_id = %(uid)s AND p.undone_at IS NULL ORDER BY p.passed_at DESC, p.id DESC LIMIT 1) "
        "    AS last_passed",
        {"code": v.code, "uid": v.user_id},
    ).fetchone()
    assert row is not None
    return {"joined": int(row["joined"]), "pending": int(row["pending"]), "passed": int(row["passed"]),
            "asked": int(row["asked"]), "last_passed": row["last_passed"]}  # fmt: skip


def your_crews(conn: Conn, v: Viewer) -> dict[str, Any]:
    """L-CREW/9: ideas the person is on or has asked to join (a team-up request, or a draft's merge request that
    waits, BLD-F038), newest first, one row per idea, each with its state ("Waiting for Ravi", "On the crew"), and
    the link to My ideas → Teamed up."""
    if not v.code:
        return {"items": [], "teamed_link": TEAMED_LINK}
    lead_of = (
        "coalesce((SELECT l.contributor_code FROM crew_members l WHERE l.idea_uuid = i.id AND l.role = 'lead' "
        "AND l.left_at IS NULL LIMIT 1), i.contributor_code)"
    )
    rows = conn.execute(
        f"SELECT i.idea_id, i.title, i.status, 'on_crew' AS state, m.joined_at AS at, NULL::text AS request_id, "  # noqa: S608 (fixed SQL)
        f"  {lead_of} AS lead_code "
        f"FROM crew_members m JOIN ideas i ON i.id = m.idea_uuid "
        f"WHERE m.contributor_code = %(code)s AND m.left_at IS NULL AND m.role = 'crew' AND i.idea_id IS NOT NULL "
        f"UNION ALL "
        f"SELECT i.idea_id, i.title, i.status, 'waiting', t.sent_at, t.id::text, {lead_of} "
        f"FROM teamup_requests t JOIN ideas i ON i.id = t.idea_uuid "
        f"WHERE t.from_code = %(code)s AND t.state = 'sent' AND i.idea_id IS NOT NULL "
        f"UNION ALL "
        f"SELECT i.idea_id, i.title, i.status, 'waiting', mr.sent_at, mr.id::text, {lead_of} "
        f"FROM merge_requests mr JOIN ideas i ON i.id = mr.other_idea_uuid "
        f"WHERE mr.from_code = %(code)s AND mr.state = 'waiting' AND i.idea_id IS NOT NULL "
        f"ORDER BY at DESC",
        {"code": v.code},
    ).fetchall()
    # BLD-F042: a crew the person is on shows its lead's name (crews see each other's names in the conversation);
    # a request still waiting follows the card it came from, so a hidden name stays hidden there.
    on_codes = sorted({str(r["lead_code"]) for r in rows if r["state"] != "waiting"})
    waiting_codes = sorted({str(r["lead_code"]) for r in rows if r["state"] == "waiting"})
    named = person_refs(conn, on_codes, names_always=True)
    shown = person_refs(conn, waiting_codes, names_always=False)
    items = []
    seen: set[str] = set()
    for r in rows:
        # On the crew and still waiting on a draft's merge request: one row per idea, the newest.
        if r["idea_id"] in seen:
            continue
        seen.add(r["idea_id"])
        waiting = r["state"] == "waiting"
        lead = (shown if waiting else named)[str(r["lead_code"])]
        hidden = lead["name"] == HIDDEN_NAME
        label = (
            ("Waiting for the lead" if hidden else f"Waiting for {lead['first_name']}")
            if waiting
            else "On the crew"
        )
        items.append({
            "id": r["idea_id"], "title": mask_text(r["title"]).strip() or r["idea_id"], "status": r["status"],
            "lead": dict(lead),
            "state": r["state"], "label": label, "request_id": r["request_id"], "at": r["at"].isoformat(),
        })  # fmt: skip
    return {"items": items, "teamed_link": TEAMED_LINK}


def deck(
    conn: Conn,
    user_id: str,
    filters: Mapping[str, Iterable[str]] | None = None,
    *,
    limit: int | None = None,
    now: dt.datetime | None = None,
    include_crews: bool = True,
) -> dict[str, Any]:
    """`GET /crew` (A-API.team-up): the cards after filters (`items`, `total` for "Show N ideas" and "N ideas close
    to yours"), every filter with live counts (`filters`, and flat `counts` as "<key>:<value>"), the active ones
    (`active`), the person's tallies, the deck's state and "Your crews".

    `state` is `cards` while any card is left before filters; once none is, `everyone_seen` if the person has
    passed, asked or joined anything (L-CREW/7), else `nothing_yet` (L-CREW/8, BLD-F033). Requested cards count as
    cards everywhere: in the filters, their counts and `total` (DEC-126). `limit` reads the deck as `limited` says."""
    current = now or _now()
    v = viewer(conn, user_id)
    cards = cards_for(conn, v, current)
    active = normalise(filters)
    shown = [c for c in cards if _matches(c, active)]
    t = tallies(conn, v)
    if cards:
        state = "cards"
    elif t["passed"] or t["asked"] or t["joined"] or t["pending"]:
        state = "everyone_seen"
    else:
        state = "nothing_yet"
    groups = facet_groups(cards, active)
    body: dict[str, Any] = {
        "items": [c.as_json() for c in limited(shown, limit)],
        "total": len(shown),
        "counts": {f"{g['key']}:{o['value']}": o["count"] for g in groups for o in g["options"]},
        "filters": groups,
        "active": chips(active),
        "deck_total": len(cards),
        "state": state,
        **t,
    }
    if include_crews:
        body["your_crews"] = your_crews(conn, v)
    return body


def home(conn: Conn, user_id: str, limit: int = 3, now: dt.datetime | None = None) -> dict[str, Any]:
    """L-CREW/10, A-API.home `crew`: the deck's first `limit` cards (with the latest requested card last, `limited`)
    and how many there are in all."""
    d = deck(conn, user_id, limit=limit, now=now, include_crews=False)
    return {"total": d["deck_total"], "top": d["items"]}


# ---------------------------------------------------------------------------------------------------------------
# Passes (L-CREW/6)
# ---------------------------------------------------------------------------------------------------------------
def _passed(conn: Conn, user_id: str) -> tuple[int, str | None]:
    row = conn.execute(
        "SELECT count(*) AS n, (SELECT i.idea_id FROM crew_passes p JOIN ideas i ON i.id = p.idea_uuid "
        "  WHERE p.user_id = %(uid)s AND p.undone_at IS NULL ORDER BY p.passed_at DESC, p.id DESC LIMIT 1) AS last "
        "FROM crew_passes WHERE user_id = %(uid)s AND undone_at IS NULL",
        {"uid": user_id},
    ).fetchone()
    assert row is not None
    return int(row["n"]), row["last"]


def pass_idea(conn: Conn, user_id: str, idea_ref: object) -> dict[str, Any]:
    """ "Next" passes the front card; passing it again changes nothing. Only a colleague's shared idea can be
    passed."""
    v = viewer(conn, user_id)
    if not isinstance(idea_ref, str) or not idea_ref.strip():
        raise Refused(422, "idea_required", field="idea_id")
    row = conn.execute(
        "SELECT id, contributor_code, shared_at, status FROM ideas WHERE idea_id = %s", (idea_ref.strip(),)
    ).fetchone()
    if (
        row is None
        or row["shared_at"] is None
        or row["status"] == "draft"
        or row["contributor_code"] == v.code
    ):
        raise Refused(404, "not_found")
    conn.execute(
        "INSERT INTO crew_passes (user_id, idea_uuid) VALUES (%s, %s) "
        "ON CONFLICT (user_id, idea_uuid) WHERE undone_at IS NULL DO NOTHING",
        (v.user_id, row["id"]),
    )
    n, last = _passed(conn, v.user_id)
    return {"passed": n, "last_passed": last}


def undo_last(conn: Conn, user_id: str, now: dt.datetime | None = None) -> dict[str, Any]:
    """ "Undo last pass" brings the last passed card back (`card`, when it is still one the person could join);
    with nothing passed it changes nothing (`restored` is null)."""
    v = viewer(conn, user_id)
    row = conn.execute(
        "UPDATE crew_passes SET undone_at = now() WHERE id = ("
        "  SELECT id FROM crew_passes WHERE user_id = %s AND undone_at IS NULL "
        "  ORDER BY passed_at DESC, id DESC LIMIT 1 FOR UPDATE) "
        "RETURNING idea_uuid::text AS idea_uuid, (SELECT idea_id FROM ideas WHERE id = crew_passes.idea_uuid) AS ref",
        (v.user_id,),
    ).fetchone()
    card = None
    if row is not None:
        card = next(
            (c.as_json() for c in cards_for(conn, v, now or _now()) if c.uuid == row["idea_uuid"]), None
        )
    n, last = _passed(conn, v.user_id)
    return {"restored": row["ref"] if row else None, "card": card, "passed": n, "last_passed": last}


def reset(conn: Conn, user_id: str) -> dict[str, Any]:
    """ "See them again": every pass is undone; the cards come back in deck order."""
    v = viewer(conn, user_id)
    cur = conn.execute(
        "UPDATE crew_passes SET undone_at = now() WHERE user_id = %s AND undone_at IS NULL", (v.user_id,)
    )
    return {"reset": cur.rowcount, "passed": 0, "last_passed": None}
