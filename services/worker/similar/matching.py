"""Matching similar ideas (L-SIMILAR, BLD-C092): for a draft while it is written (S-04B's strip, Check it part 3)
and again after sharing ("Checked and matched"), against every shared idea that is not withdrawn.

1. Query: the draft's masked title, short summary and the person's masked words (`idea_messages`, the masked
   copy), masked once more. Nothing is read from the company repo.
2. Retrieval over the ideas' own chunks (`similar.index`): meaning (cosine, above the floor) and keywords, fused by
   reciprocal rank. A hit on a merged idea resolves to the surviving idea. The person's own ideas never match.
3. Labels: the `judge` agent, through the gateway (`run_agent`; the payload is tagged first): `same` -> `close`,
   `related` -> `related`, `different` -> dropped. The judge sees each side's masked title and short summary only,
   never the person's messages, because its phrase is read by both sharers (DEC-104, BLD-C097). With the assistant
   off (`ai.all`) or the judge failing, the strength comes from code: cosine for `close`, cosine or shared keywords
   for `related`.
4. The reason ("Close match: same SMS, same calls") is the judge's short phrase if it passes the tag, pattern and
   name checks, else one built by code from the words the two ideas share. It is shown to both sharers.
5. At most 8, `close` first, kept in `similar_links` with the run in `similar_runs`. A run that fails is recorded
   and never blocks sharing (`L-SIMILAR.failure`); the next run, at the latest after sharing, tries again. Every
   step from the lookup on runs in one savepoint, so nothing here can abort the caller's transaction (BLD-C096).

Logs carry IDs and counts only (non-negotiable 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from core import killswitch
from core.config import get_settings
from core.crypto import keyed_hash
from core.db import Conn, vector_literal
from core.logging import get_logger
from embeddings import embed
from onepc.context import open_text
from similar import IdeaNotFound, index
from similar.preview import IDEA_REF, checked_sentence, mask_text

log = get_logger("similar")

FoundWhile = Literal["drafting", "checking", "later"]
Strength = Literal["close", "related"]

MAX_MATCHES = 8  # L-SIMILAR.rules/3
TO_JUDGE = 12  # candidates sent to the judge (its schema allows 20)
MIN_CHARS = 50  # a draft is matched once it has this much to go on (mapping/logic.md, L-SIMILAR row)
QUERY_CHARS = 2000
TITLE_CHARS = 160  # what the judge reads of each side (BLD-C097)
SUMMARY_CHARS = 480
CLOSE_COSINE = 0.80  # code-only `close`: near-identical meaning (BGE-M3); the judge decides when it runs
RELATED_SHARED_WORDS = 2  # code-only `related` on keywords alone: at least this many shared words …
RELATED_OVERLAP = 0.25  # … making up at least this share of the other idea's words
CLOSE_SHARED_WORDS = 4  # code-only `close` on words: near-identical wording
CLOSE_OVERLAP = 0.6
REASON_WORDS = 14
NEVER_MATCH = ("draft", "withdrawn")
DEFAULTS = {"cosine_floor": 0.45, "top_k_each": 50, "rrf_k": 60, "rerun_if_edit_share": 0.2}

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]{2,}")
STOP = frozenset(
    ["the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "had", "her", "his", "was", "one", "our", "out", "has", "have", "this", "that", "with", "from", "they", "will", "what", "when", "your", "into", "than", "then", "them", "were", "been", "more", "some", "such", "only", "also", "very", "just", "over", "each", "about", "which", "would", "could", "should", "there", "their", "these", "those", "because", "every", "who", "why", "how", "get", "gets", "got", "its", "a", "an", "is", "it", "to", "of", "in", "on", "at", "by", "or", "as", "be", "we", "us", "so", "if", "no", "do", "does", "did", "after", "before", "again", "same", "time", "times", "day", "days", "week", "weeks", "month", "need", "needs", "want", "make", "makes", "people", "someone", "here", "now", "many", "much", "still", "even", "where", "while", "until", "without"]
)  # fmt: skip


@dataclass
class Hit:
    uuid: str
    ref: str
    title: str
    summary: str
    area: str
    status: str
    score: float = 0.0
    cosine: float = 0.0
    keyword: bool = False


@dataclass
class Found:
    uuid: str
    strength: Strength
    reason: str
    score: float


@dataclass
class Run:
    state: Literal["done", "failed", "too_short", "unchanged"]
    found: int = 0
    labelled_by: Literal["judge", "code"] | None = None
    matches: list[Found] = field(default_factory=list)


# ---- inputs ------------------------------------------------------------------------------------------------------


def _settings() -> dict[str, float]:
    from rules import load_rule

    try:
        data = dict(load_rule(get_settings().company_repo_path, "thresholds").data["match"])
    except Exception:  # missing or broken configuration must not stop matching (L-SIMILAR.failure)
        data = {}
    return {k: float(data.get(k, v)) for k, v in DEFAULTS.items()}


def _idea(conn: Conn, idea_uuid: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT id, idea_id, contributor_code, status, kind, title, summary, area, affects, shared_at, "
        "canvas->>'neutral_summary' AS neutral_summary FROM ideas WHERE id = %s",
        (idea_uuid,),
    ).fetchone()
    return dict(row) if row else None


def masked_words(conn: Conn, idea_uuid: str) -> str:
    """The person's own words, the masked copy (DEC-103), in order."""
    rows = conn.execute(
        "SELECT id, text_encrypted FROM idea_messages WHERE idea_uuid = %s ORDER BY seq", (idea_uuid,)
    ).fetchall()
    texts = (open_text("idea_messages", "text_encrypted", str(r["id"]), r["text_encrypted"]) for r in rows)
    return "\n".join(t for t in texts if t)


def query_text(conn: Conn, idea: dict[str, Any]) -> str:
    parts = (
        idea.get("title"),
        idea.get("summary") or idea.get("neutral_summary"),
        masked_words(conn, idea["id"]),
    )
    return mask_text("\n\n".join(str(p) for p in parts if p))[:QUERY_CHARS].strip()


def words(text: str) -> list[str]:
    """Content words in order, lower case, each once."""
    return list(dict.fromkeys(w for w in (m.lower() for m in _WORD.findall(text)) if w not in STOP))


def word_hashes(text: str) -> list[str]:
    return sorted({keyed_hash("similar-words", w).hex()[:12] for w in words(text)})


def material_change(before: list[str], after: list[str], share: float) -> bool:
    """L-SIMILAR.rules/4: re-run when at least `share` of the words changed (symmetric difference over union)."""
    a, b = set(before), set(after)
    union = a | b
    return bool(union) and len(a ^ b) / len(union) >= share


# ---- retrieval ---------------------------------------------------------------------------------------------------


def _keyword_query(text: str) -> str:
    return " or ".join(words(text)[:40])


def survivor(conn: Conn, idea_uuid: str) -> dict[str, Any] | None:
    """The idea a hit stands for: itself, or the idea it was merged into (followed up to five merges)."""
    seen: set[str] = set()
    current = idea_uuid
    for _ in range(6):
        row = conn.execute(
            "SELECT id, idea_id, contributor_code, status, title, summary, area, merged_into, shared_at, "
            "canvas->>'neutral_summary' AS neutral_summary FROM ideas WHERE id = %s",
            (current,),
        ).fetchone()
        if row is None or str(row["id"]) in seen:
            return None
        seen.add(str(row["id"]))
        if row["status"] == "merged" and row["merged_into"] is not None:
            current = str(row["merged_into"])
            continue
        ok = row["idea_id"] is not None and row["shared_at"] is not None and row["status"] not in NEVER_MATCH
        return dict(row) if ok else None
    return None


def retrieve(
    conn: Conn, idea: dict[str, Any], text: str, owner_codes: set[str], *,
    vec: list[float] | None = None, settings: dict[str, float] | None = None,
) -> list[Hit]:  # fmt: skip
    """Candidates by meaning and keywords over the ideas' chunks, merged ideas resolved, own ideas left out.
    `vec` is the query's embedding when the caller already has it (one embedding per run)."""
    s = settings or _settings()
    floor, top_k, rrf_k = s["cosine_floor"], int(s["top_k_each"]), s["rrf_k"]
    vec = vec if vec is not None else embed([text])[0]
    with conn.transaction():
        conn.execute("SET LOCAL hnsw.ef_search = 400")
        conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        vector_rows = conn.execute(
            "SELECT idea_uuid, 1 - (embedding <=> %s::vector) AS cos FROM chunks WHERE idea_uuid IS NOT NULL "
            "ORDER BY embedding <=> %s::vector LIMIT %s",
            (vector_literal(vec), vector_literal(vec), top_k),
        ).fetchall()
    cosine = {str(r["idea_uuid"]): float(r["cos"]) for r in vector_rows}
    by_meaning = [u for u, c in sorted(cosine.items(), key=lambda kv: -kv[1]) if c >= floor]
    query = _keyword_query(text)
    by_words = (
        [
            str(r["idea_uuid"])
            for r in conn.execute(
                "SELECT idea_uuid, ts_rank_cd(tsv, q) AS rank FROM chunks, websearch_to_tsquery('simple', %s) q "
                "WHERE idea_uuid IS NOT NULL AND tsv @@ q ORDER BY rank DESC, idea_uuid LIMIT %s",
                (query, top_k),
            ).fetchall()
        ]
        if query
        else []
    )
    fused: dict[str, float] = {}
    for ranked in (by_meaning, by_words):
        for rank, u in enumerate(ranked, start=1):
            fused[u] = fused.get(u, 0.0) + 1.0 / (rrf_k + rank)
    keyword_hits = set(by_words)

    hits: dict[str, Hit] = {}
    for u, score in fused.items():
        row = survivor(conn, u)
        if row is None or str(row["id"]) == str(idea["id"]) or row["contributor_code"] in owner_codes:
            continue
        key = str(row["id"])
        hit = hits.get(key) or Hit(
            uuid=key,
            ref=str(row["idea_id"]),
            title=mask_text(row["title"]).strip(),
            summary=mask_text(row["summary"] or row["neutral_summary"]).strip(),
            area=str(row["area"] or ""),
            status=str(row["status"]),
        )
        hit.score = max(hit.score, score)
        hit.cosine = max(hit.cosine, cosine.get(u, 0.0))
        hit.keyword = hit.keyword or u in keyword_hits
        hits[key] = hit
    return sorted(hits.values(), key=lambda h: (-h.score, h.ref))


# ---- labels ------------------------------------------------------------------------------------------------------


def shared_words(mine: str, hit: Hit) -> list[str]:
    """Words the two ideas share, the other idea's title first: what the reason line names. A word the other idea
    writes in capitals or with digits ("SMS", "R07") keeps that form; any other is lower case."""
    own = set(words(mine))
    theirs = f"{hit.title}\n{hit.summary}"
    written = {m.lower(): m for m in reversed(_WORD.findall(theirs))}
    return [_display(written.get(w, w)) for w in words(theirs) if w in own]


def _display(word: str) -> str:
    return word if word.isupper() or not word.isalpha() else word.lower()


def overlap(hit: Hit, shared: list[str]) -> float:
    """The share of the other idea's words that this one shares (title and summary)."""
    return len(shared) / max(1, len(words(f"{hit.title}\n{hit.summary}")))


def code_strength(hit: Hit, shared: list[str], floor: float) -> Strength | None:
    """With the assistant off (`ai.all`, D1): meaning first (cosine), then words. Shared words alone make a match
    only when they are a good part of the other idea, so one common word ("investors") is never enough."""
    share = overlap(hit, shared)
    if hit.cosine >= CLOSE_COSINE or (len(shared) >= CLOSE_SHARED_WORDS and share >= CLOSE_OVERLAP):
        return "close"
    if hit.cosine >= floor or (
        hit.keyword and len(shared) >= RELATED_SHARED_WORDS and share >= RELATED_OVERLAP
    ):
        return "related"
    return None


def code_reason(strength: Strength, shared: list[str], area: str, same_area: bool) -> str:
    """Plain words that name what is shared, the same for both sharers."""
    picked = shared[:2]
    if strength == "close":
        return "Close match: " + (", ".join(f"same {w}" for w in picked) if picked else "the same problem")
    if picked:
        return "Related: also about " + " and ".join(picked)
    if same_area and area:
        return f"Related: also in {area}"
    return "Related: a similar problem"


def judge_reason(conn: Conn, strength: Strength, reason: Any) -> str | None:
    """The judge's phrase as the line both sharers read, if it passes the checks and is short."""
    phrase = " ".join(str(reason or "").split()).rstrip(".").strip()
    if not phrase or len(phrase.split()) > REASON_WORDS:
        return None
    phrase = phrase[0].lower() + phrase[1:] if phrase[:2] != phrase[:2].upper() else phrase
    line = ("Close match: " if strength == "close" else "Related: ") + phrase
    return checked_sentence(conn, line)


def judge_text(idea: dict[str, Any]) -> tuple[str, str]:
    """What the judge sees of the draft or idea: its masked title and short summary, trimmed as the candidates'
    are. Never the person's messages: the judge's phrase is read by both sharers, and a word only in this
    person's messages must not reach the other one (DEC-104, non-negotiable 7, BLD-C097)."""
    title = " ".join(mask_text(idea.get("title")).split())[:TITLE_CHARS]
    summary = " ".join(mask_text(idea.get("summary") or idea.get("neutral_summary")).split())[:SUMMARY_CHARS]
    return title, summary


def judge(
    conn: Conn, idea: dict[str, Any], hits: list[Hit], vec: list[float]
) -> dict[str, dict[str, Any]] | None:
    """The judge's labels by IDEA- reference, or None when it is off, failed or has nothing to read (the caller
    labels by code). `vec` (the query's embedding) only finds the reviewers' past corrections."""
    from gateway import AgentFailed, run_agent
    from router.corrections import corrections_for

    if not hits or not killswitch.is_on("ai.all", conn) or not killswitch.is_on("agent.judge", conn):
        return None
    one_line, details = judge_text(idea)
    if not (one_line or details):
        return None
    card = {
        "kind": idea.get("kind"),
        "one_line": one_line,
        "details": details,
        "who": {"segments": list(idea.get("affects") or [])},
        "category": None,
        "play": None,
        "areas": [idea["area"]] if idea.get("area") else [],
        "lobs": [],
        "systems": [],
    }
    candidates = [
        {
            "cid": h.ref,
            "type": "idea",
            "title": h.title[:TITLE_CHARS],
            "summary": " ".join(h.summary.split())[:SUMMARY_CHARS],
            "stage": h.status,
            "areas": [h.area] if h.area else [],
            "lobs": [],
        }
        for h in hits
        if IDEA_REF.match(h.ref)
    ]
    scope = str(idea["idea_id"]) if idea.get("idea_id") else f"DRAFT-{idea['id']}"
    try:
        out = run_agent(
            "judge",
            {
                "card": card,
                "candidates": candidates,
                "past_corrections": corrections_for(conn, vec, field="match"),
            },
            scope,
            conn=conn,
        )
    except AgentFailed as exc:
        log.info("similar.judge_skipped", idea_uuid=str(idea["id"]), error_code=exc.code)
        return None
    return {str(r["cid"]): r for r in out.data.get("results") or []}


def label(
    conn: Conn, idea: dict[str, Any], text: str, hits: list[Hit], *,
    vec: list[float] | None = None, settings: dict[str, float] | None = None,
) -> tuple[list[Found], str]:  # fmt: skip
    """Strength and reason per hit, close first, at most MAX_MATCHES. Returns (found, labelled_by). The code
    reason names only the other idea's own title and summary words, so it is safe for both sharers."""
    floor = (settings or _settings())["cosine_floor"]
    sent = hits[:TO_JUDGE]
    labels = judge(conn, idea, sent, vec if vec is not None else embed([text])[0])
    found: list[Found] = []
    for h in sent if labels is not None else hits:
        shared = shared_words(text, h)
        strength: Strength | None
        reason: str | None = None
        if labels is not None:
            verdict = labels.get(h.ref) or {}
            strength = {"same": "close", "related": "related"}.get(str(verdict.get("label")))  # type: ignore[assignment]
            if strength:
                reason = judge_reason(conn, strength, verdict.get("reason"))
        else:
            strength = code_strength(h, shared, floor)
        if strength is None:
            continue
        if reason is None:
            reason = checked_sentence(
                conn, code_reason(strength, shared, h.area, h.area == (idea.get("area") or ""))
            ) or ("Close match: the same problem" if strength == "close" else "Related: a similar problem")
        found.append(Found(h.uuid, strength, reason, h.score))
    found.sort(key=lambda f: (f.strength != "close", -f.score))
    return found[:MAX_MATCHES], ("judge" if labels is not None else "code")


# ---- runs --------------------------------------------------------------------------------------------------------


def owner_codes(conn: Conn, code: str) -> set[str]:
    """Every contributor code of the person behind `code` (one today; a re-hire could have two)."""
    rows = conn.execute(
        "SELECT m2.contributor_code FROM contributor_map m JOIN contributor_map m2 ON m2.user_id = m.user_id "
        "WHERE m.contributor_code = %s",
        (code,),
    ).fetchall()
    return {code, *(str(r["contributor_code"]) for r in rows)}


def save(conn: Conn, idea_uuid: str, found: list[Found], found_while: FoundWhile) -> None:
    """Upsert the links (the first `found_while` is kept), drop the ones no longer found unless the person acted
    on them ("Keep mine separate", a merge request)."""
    for rank, f in enumerate(found, start=1):
        conn.execute(
            "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason, rank, found_while) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (idea_uuid, other_idea_uuid) DO UPDATE SET "
            "strength = EXCLUDED.strength, reason = EXCLUDED.reason, rank = EXCLUDED.rank",
            (idea_uuid, f.uuid, f.strength, f.reason, rank, found_while),
        )
    conn.execute(
        "DELETE FROM similar_links WHERE idea_uuid = %s AND NOT (other_idea_uuid = ANY(%s::uuid[])) "
        "AND (outcome IS NULL OR outcome = 'previewed')",
        (idea_uuid, [f.uuid for f in found]),
    )


def _record(
    conn: Conn, idea_uuid: str, state: str, found_while: FoundWhile, labelled_by: str | None,
    hashes: list[str], found: int, error_code: str | None,
) -> None:  # fmt: skip
    conn.execute(
        "INSERT INTO similar_runs (idea_uuid, state, found_while, labelled_by, word_hashes, found, error_code) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (idea_uuid) DO UPDATE SET state = EXCLUDED.state, "
        "found_while = EXCLUDED.found_while, labelled_by = EXCLUDED.labelled_by, word_hashes = EXCLUDED.word_hashes, "
        "found = EXCLUDED.found, error_code = EXCLUDED.error_code, ran_at = now()",
        (idea_uuid, state, found_while, labelled_by, hashes, found, error_code),
    )


def match_idea(
    conn: Conn,
    idea_uuid: str,
    *,
    found_while: FoundWhile = "drafting",
    force: bool = False,
    title: str | None = None,
    summary: str | None = None,
) -> Run:
    """Match a draft or an idea and keep the result (L-SIMILAR.rules/4, /5). Never raises for a matching failure:
    it is recorded as `failed` (L-SIMILAR.failure) and the caller carries on. Safe inside the caller's transaction:
    everything from the lookup on runs in one savepoint, so a decrypt error, a database error or a missing row here
    never aborts it (BLD-C096). Raises `IdeaNotFound` (a LookupError) for an unknown ID, after the savepoint is
    rolled back.

    `title` and `summary` stand in for the row's (a draft run passes its newest title part). Skipped (`unchanged`)
    when the last run succeeded and the words changed less than `rerun_if_edit_share`, at the same point or after an
    edit (`later`); `force` runs anyway. Sharing (`checking`) always runs."""
    hashes: list[str] = []
    try:
        with conn.transaction():  # a savepoint inside the caller's transaction
            idea = _idea(conn, idea_uuid)
            if idea is None:
                raise IdeaNotFound("idea_not_found")
            if title is not None:
                idea["title"] = title or idea.get("title")
            if summary is not None:
                idea["summary"] = summary or idea.get("summary")
            text = query_text(conn, idea)
            if len(text) < MIN_CHARS:
                return Run("too_short")
            hashes = word_hashes(text)
            settings = _settings()
            last = conn.execute(
                "SELECT state, found_while, word_hashes, found, labelled_by FROM similar_runs WHERE idea_uuid = %s",
                (idea_uuid,),
            ).fetchone()
            if (
                not force
                and found_while != "checking"
                and last is not None
                and last["state"] == "done"
                and (last["found_while"] == found_while or found_while == "later")
                and not material_change(list(last["word_hashes"]), hashes, settings["rerun_if_edit_share"])
            ):
                return Run("unchanged", int(last["found"]), last["labelled_by"])
            index.sync(conn)
            vec = embed([text])[0]  # once per run: retrieval and the judge's past corrections
            owners = owner_codes(conn, str(idea["contributor_code"]))
            hits = retrieve(conn, idea, text, owners, vec=vec, settings=settings)
            found, labelled_by = label(conn, idea, text, hits, vec=vec, settings=settings)
            save(conn, idea_uuid, found, found_while)
            _record(conn, idea_uuid, "done", found_while, labelled_by, hashes, len(found), None)
    except IdeaNotFound:
        raise
    except Exception as exc:
        log.error("similar.match_failed", idea_uuid=idea_uuid, error_type=type(exc).__name__)
        try:
            with conn.transaction():
                _record(conn, idea_uuid, "failed", found_while, None, hashes, 0, type(exc).__name__)
        except Exception as again:  # the caller's transaction may be unusable; sharing still goes on
            log.error("similar.record_failed", idea_uuid=idea_uuid, error_type=type(again).__name__)
        return Run("failed")
    log.info(
        "similar.matched", idea_uuid=idea_uuid, found_count=len(found), labelled_by=labelled_by,
        found_while=found_while,
    )  # fmt: skip
    return Run("done", len(found), labelled_by, found)  # type: ignore[arg-type]


def last_run(conn: Conn, idea_uuid: str) -> dict[str, Any] | None:
    """The stored state Check it reads: {state, found, ran_at} (L-SIMILAR.rules/4, /9)."""
    row = conn.execute(
        "SELECT state, found, found_while, ran_at FROM similar_runs WHERE idea_uuid = %s", (idea_uuid,)
    ).fetchone()
    return dict(row) if row else None
