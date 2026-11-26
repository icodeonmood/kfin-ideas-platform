"""Find the values to tag before any model call (ARCHITECTURE §3.2 step 1). Detection runs inside KFin only.

Sources, in priority order (a higher-priority find wins an overlap; then the longer span):
1. The shared §4.2 patterns: identifiers and contact details.
2. Contributor and reviewer codes.
3. Colleagues from `users`: full names and email addresses.
4. Client organisations from the company repo's `taxonomy/clients/` (names and aliases).
5. Other person names: Microsoft Presidio with the small spaCy English model, plus two KFin recognisers
   (honorifics such as "Shri" or "Mrs", and a lexicon of common Indian given names and surnames, because the
   small model often labels Indian names as organisations or places). BLD-067.

Not tagged: KFin product and system names (the glossary), public competitor and vendor names, amounts, dates.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.db import Conn
from okf.frontmatter import parse
from pii.patterns import scan

NAMES_DIR = Path(__file__).parent / "names"

PATTERN_TYPES = {
    "pan": "PAN",
    "aadhaar": "AADHAAR",
    "mobile": "PHONE",
    "email": "EMAIL",
    "bank_account": "ACCOUNT_NUMBER",
    "card": "CARD_NUMBER",
    "folio": "FOLIO_NUMBER",
    "demat_in": "DEMAT_ACCOUNT",
    "demat_16": "DEMAT_ACCOUNT",
    "pran": "PRAN",
    "dob": "DATE_OF_BIRTH",
    "ifsc": "IFSC",
    "arn": "ARN",
    "euin": "EUIN",
}
CLIENT_TYPES = {
    "amc": "CLIENT_AMC",
    "issuer": "CLIENT_ISSUER",
    "fund_manager": "CLIENT_FUND_MANAGER",
    "pension": "CLIENT_PENSION",
    "partner": "CLIENT_PARTNER",
}
CODE_RE = re.compile(r"\b(?:CTR-[0-9a-f]{6,8}|REV-[0-9]{4})\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DIRECTORY_TTL_S = 60.0
ROLE_WORDS = frozenset(
    {
        "customer", "investor", "distributor", "client", "nominee", "unitholder", "holder", "agent", "broker",
        "colleague", "manager", "sir", "madam", "mr", "mrs", "ms", "dr", "shri", "smt", "sri",
    }
)  # fmt: skip

# The platform's own IDs are never names, though the NER model sometimes reads one as a PERSON ("CL-0010"
# tagged as a person broke the judge's candidate IDs, BLD-221). Only an exact match is skipped. That includes the
# short refs the gateway hands agents for the items in a payload, which the NER model reads as people at random
# ("M13", "M17", "I15", "I28"): tagged, they break the output's refs, so every group of 13 or more ideas failed
# cluster-summary and switched it off (BLD-160).
PLATFORM_ID = re.compile(
    r"(?:IDEA|SUB)-[0-9]{4}-[0-9]{6}|(?:CL|SOL|REV|WG)-[0-9]{4}|(?:DEC|RND|PRS|APL)-[0-9]{4}-[0-9]{4}"
    r"|CYC-[0-9]{4}-[0-9]{2}(?:-[0-9]+)?|RUN-[0-9]{4}-W[0-9]{2}(?:-[0-9]+)?"
    r"|[MI][0-9]{1,2}|(?:Member|Contributor) [0-9]{1,2}"
)


@dataclass(frozen=True)
class Found:
    start: int
    end: int
    type: str
    value: str
    priority: int
    subject_user_id: str | None = None


@dataclass
class Directory:
    """Who and what to recognise: colleagues, client organisations and terms that are never people."""

    employee_names: dict[str, str] = field(default_factory=dict)  # normalised full name -> user id
    employee_emails: dict[str, str] = field(default_factory=dict)  # lower-case email -> user id
    clients: dict[str, str] = field(default_factory=dict)  # alias (as written in the repo) -> tag type
    never_person: set[str] = field(default_factory=set)  # lower-case glossary terms and client aliases
    _name_re: re.Pattern[str] | None = None
    _client_res: list[tuple[re.Pattern[str], str]] = field(default_factory=list)

    def compile(self) -> Directory:
        names = sorted(self.employee_names, key=len, reverse=True)
        self._name_re = (
            re.compile(
                r"(?<![\w])(" + "|".join(re.escape(n).replace(r"\ ", r"\s+") for n in names) + r")(?![\w])",
                re.I,
            )
            if names
            else None
        )
        self._client_res = []
        for alias, typ in sorted(self.clients.items(), key=lambda kv: len(kv[0]), reverse=True):
            flags = 0 if (len(alias) <= 4 and alias.isupper()) else re.I  # short acronyms: exact case only
            body = re.escape(alias).replace(r"\ ", r"\s+")
            self._client_res.append((re.compile(r"(?<![\w])" + body + r"(?![\w])", flags), typ))
        return self


def normalise_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def _repo_clients_and_terms(repo: Path) -> tuple[dict[str, str], set[str]]:
    clients: dict[str, str] = {}
    terms: set[str] = set()
    for path in sorted((repo / "taxonomy" / "clients").glob("CLI-*.md")):
        meta = parse(path.read_text(encoding="utf-8")).meta or {}
        k = meta.get("kfin") or {}
        typ = CLIENT_TYPES.get(str(k.get("client_type", "")), "CLIENT_AMC")
        for alias in [meta.get("title"), *(k.get("aliases") or [])]:
            if alias and len(str(alias).strip()) >= 2:
                clients[str(alias).strip()] = typ
                terms.add(str(alias).strip().casefold())
    for path in sorted((repo / "taxonomy" / "glossary").glob("GL-*.md")):
        meta = parse(path.read_text(encoding="utf-8")).meta or {}
        k = meta.get("kfin") or {}
        for t in [meta.get("title"), k.get("term"), *(k.get("aliases") or [])]:
            if t:
                terms.add(str(t).strip().casefold())
    return clients, terms


def build_directory(conn: Conn, repo: Path | None = None) -> Directory:
    repo = repo or get_settings().company_repo_path
    d = Directory()
    for row in conn.execute("SELECT id, name, email FROM users").fetchall():
        if row["name"] and len(row["name"].split()) >= 2:
            d.employee_names[normalise_name(row["name"])] = str(row["id"])
        if row["email"]:
            d.employee_emails[row["email"].lower()] = str(row["id"])
    if repo and repo.exists():
        d.clients, d.never_person = _repo_clients_and_terms(repo)
    return d.compile()


_cache: dict[str, tuple[float, str, Directory]] = {}
_cache_lock = threading.Lock()


def _users_signature(conn: Conn) -> str:
    """Cheap fingerprint of the people table: a colleague added or renamed a moment ago is caught at once
    (Ones review: a stale directory let a new colleague's name through the public-text check)."""
    row = conn.execute(
        "SELECT count(*) AS n, max(updated_at) AS m, max(created_at) AS c FROM users"
    ).fetchone()
    return f"{row['n']}|{row['m']}|{row['c']}" if row else ""


def directory(conn: Conn, repo: Path | None = None) -> Directory:
    """The directory, rebuilt when the people table changes and at least once a minute per database and repo."""
    key = f"{conn.info.dsn}|{repo or get_settings().company_repo_path}"
    sig = _users_signature(conn)
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[1] == sig and time.monotonic() - hit[0] < DIRECTORY_TTL_S:
            return hit[2]
    d = build_directory(conn, repo)
    with _cache_lock:
        _cache[key] = (time.monotonic(), sig, d)
    return d


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


# ---- person names: Presidio + KFin recognisers ---------------------------------------------------------------


@lru_cache(maxsize=1)
def _lexicon() -> tuple[frozenset[str], frozenset[str]]:
    def read(name: str) -> frozenset[str]:
        lines = (NAMES_DIR / name).read_text(encoding="utf-8").splitlines()
        return frozenset(ln.strip().casefold() for ln in lines if ln.strip())

    return read("given.txt"), read("surnames.txt")


_CAP_RUN = re.compile(r"\b[A-Z][a-z'’]+(?:\s+[A-Z][a-z'’]+){0,3}\b")
_HONORIFIC = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Shri|Smt|Sri|Kumari|Km|Prof)\.?\s+([A-Z][a-z'’]+(?:\s+[A-Z][a-z'’]+){0,2})"
)


def _lexicon_people(text: str, stop: frozenset[str]) -> list[tuple[int, int, float]]:
    given, surnames = _lexicon()
    out = []
    for run in _CAP_RUN.finditer(text):
        tokens = [
            (m.start() + run.start(), m.end() + run.start(), m.group(0))
            for m in re.finditer(r"\S+", run.group(0))
        ]
        hits = [i for i, (_, _, t) in enumerate(tokens) if t.casefold() in given or t.casefold() in surnames]
        if not hits:
            continue
        first, last = hits[0], hits[-1]
        # "Ramanathan Iyer": a known surname takes the capitalised word before it; "Ravi Ramanathan": a known
        # given name takes the one after it. Common words ("Ask", "The") are never pulled in.
        if tokens[first][2].casefold() in surnames and tokens[first][2].casefold() not in given:
            while first > 0 and tokens[first - 1][2].casefold() not in stop:
                first -= 1
        if tokens[last][2].casefold() in given and tokens[last][2].casefold() not in surnames:
            while last < len(tokens) - 1 and tokens[last + 1][2].casefold() not in stop:
                last += 1
        both = any(tokens[i][2].casefold() in given for i in hits) and any(
            tokens[i][2].casefold() in surnames for i in hits
        )
        out.append((tokens[first][0], tokens[last][1], 0.85 if both or last > first else 0.6))
    return out


# ---- names written in Devanagari (DEC-139 (d), BLD-C247) ------------------------------------------------------------
# A table in the repo (names/devanagari.tsv), no new dependency. Devanagari has no capitals, so a name is a word in the
# table; a given name takes one unknown word after it and a surname one before it ("देविका रघुनाथन"), never a word
# that ends a name in Hindi (the table's `stop` rows: postpositions, "and", the verbs that follow a name, the respectful "जी").
# Other scripts wait for r8.

# Devanagari letters and signs and the joiners; never the danda (U+0964, U+0965) or the digits (U+0966 to U+096F).
_DEVA = "\u0900-\u0963\u0970-\u097f\u200c\u200d"
_DEVA_WORD = re.compile(f"[{_DEVA}]+")
# डॉक्टर is not one: it is an everyday word ("मैं डॉक्टर बनना चाहता था"), and stays a stop word.
_DEVA_HONORIFIC = re.compile(f"(?<![{_DEVA}])(?:श्रीमती|श्रीमान|सुश्री|श्री|कुमारी|डॉ[.\u0970]?)(?=[ \u00a0])")
# Folded out of every lookup key: the nukta (इरफ़ान, typed इरफान), the joiners and the abbreviation sign (डॉ॰).
_DEVA_FOLD = str.maketrans("", "", "\u093c\u200c\u200d\u0970")
_JI = "जी"  # joined to a name it is respect, not part of the name: शर्माजी


def _deva_key(word: str) -> str:
    """The form a word is looked up by: NFC, then the nukta, the joiners and the abbreviation sign folded out."""
    return unicodedata.normalize("NFC", word).translate(_DEVA_FOLD)


@lru_cache(maxsize=1)
def _deva_table() -> dict[str, frozenset[str]]:
    """names/devanagari.tsv by kind: `given`, `surname` and `stop` (the words that end a name in Hindi)."""
    kinds: dict[str, set[str]] = {"given": set(), "surname": set(), "stop": set()}
    lines = (NAMES_DIR / "devanagari.tsv").read_text(encoding="utf-8").splitlines()
    for n, line in enumerate(lines, start=1):
        if not line.strip() or line.startswith("#"):
            continue
        cells = line.split("\t")
        if len(cells) != 2 or cells[1].strip() not in kinds or not cells[0].strip():
            raise ValueError(
                f"pii/names/devanagari.tsv line {n}: expected a word, a tab, then given, surname or stop"
            )
        kinds[cells[1].strip()].add(_deva_key(cells[0].strip()))
    return {k: frozenset(v) for k, v in kinds.items()}


def _deva_lexicon() -> tuple[frozenset[str], frozenset[str]]:
    t = _deva_table()
    return t["given"], t["surname"]


def _deva_stop() -> frozenset[str]:
    return _deva_table()["stop"]


def _deva_tokens(text: str) -> list[tuple[int, int, str]]:
    """(start, end, lookup key) per Devanagari word; the spans are the text's own, only the key is folded. A name
    with जी joined to it is looked up without it, and tagged whole."""
    given, surnames = _deva_lexicon()
    names = given | surnames
    out = []
    for m in _DEVA_WORD.finditer(text):
        key = _deva_key(m.group(0))
        if key not in names and key.endswith(_JI) and key[: -len(_JI)] in names:
            key = key[: -len(_JI)]
        out.append((m.start(), m.end(), key))
    return out


def _adjacent(text: str, a: tuple[int, int, str], b: tuple[int, int, str]) -> bool:
    """Two Devanagari words with only spaces between them (no danda, comma or other word)."""
    return a[1] < b[0] and text[a[1] : b[0]].strip(" \u00a0") == ""


def _devanagari_people(text: str) -> list[tuple[int, int, float]]:
    """Person names in Devanagari: (start, end, score), as `_lexicon_people` gives them for Latin script."""
    given, surnames = _deva_lexicon()
    stop = _deva_stop()
    known = given | surnames
    tokens = _deva_tokens(text)
    out: list[tuple[int, int, float]] = []
    i = 0
    while i < len(tokens):
        if tokens[i][2] not in known or tokens[i][2] in stop:
            i += 1
            continue
        first = last = i
        while (
            last + 1 < len(tokens)
            and tokens[last + 1][2] in known
            and _adjacent(text, tokens[last], tokens[last + 1])
        ):
            last += 1
        head, tail = tokens[first][2], tokens[last][2]
        if head in surnames and head not in given and first > 0:
            before = tokens[first - 1]
            if before[2] not in stop and _adjacent(text, before, tokens[first]):
                first -= 1
        if tail in given and tail not in surnames and last + 1 < len(tokens):
            after = tokens[last + 1]
            if after[2] not in stop and _adjacent(text, tokens[last], after):
                last += 1
        names = [t[2] for t in tokens[first : last + 1]]
        both = any(n in given for n in names) and any(n in surnames for n in names)
        out.append((tokens[first][0], tokens[last][1], 0.85 if both or last > first else 0.6))
        i = last + 1
    for m in _DEVA_HONORIFIC.finditer(text):
        following = [t for t in tokens if t[0] >= m.end()][:3]
        taken: list[tuple[int, int, str]] = []
        for t in following:
            if t[2] in stop or (taken and not _adjacent(text, taken[-1], t)):
                break
            if not taken and text[m.end() : t[0]].strip(" \u00a0"):
                break
            taken.append(t)
        if taken:
            out.append((taken[0][0], taken[-1][1], 0.9))
    return _merged(text, out)


def _merged(text: str, spans: list[tuple[int, int, float]]) -> list[tuple[int, int, float]]:
    """One span per name: spans that overlap ("अमित प्रकाश" and "प्रकाश शर्मा", प्रकाश not in the table) or touch
    with only spaces between become one, as the Latin path keeps "Amit Prakash Sharma" whole. Never across a danda
    or a comma."""
    out: list[tuple[int, int, float]] = []
    for s, e, score in sorted(spans):
        if out and (s <= out[-1][1] or text[out[-1][1] : s].strip(" \u00a0") == ""):
            ps, pe, pscore = out[-1]
            out[-1] = (ps, max(pe, e), max(pscore, score))
        else:
            out.append((s, e, score))
    return out


def _deva_found(text: str, never: set[str]) -> list[Found]:
    """`_people` for a text with no capital letter: the Devanagari names only, at the same threshold."""
    out = []
    for s, e, score in _devanagari_people(text):
        value = text[s:e]
        if score >= 0.5 and value.casefold() not in never:
            out.append(Found(s, e, "PERSON", value, priority=5))
    return out


@lru_cache(maxsize=1)
def _analyzer() -> Any:
    from presidio_analyzer import AnalyzerEngine, EntityRecognizer, RecognizerRegistry, RecognizerResult
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_analyzer.predefined_recognizers import SpacyRecognizer
    from spacy.lang.en.stop_words import STOP_WORDS

    stop = frozenset(STOP_WORDS) | {"ask", "call", "contact", "email", "tell", "meet", "thanks", "dear", "hi"}

    class KfinNameRecognizer(EntityRecognizer):
        def load(self) -> None:
            return None

        def analyze(self, text: str, entities: list[str], nlp_artifacts: Any = None) -> list[Any]:
            results = [RecognizerResult("PERSON", s, e, score) for s, e, score in _lexicon_people(text, stop)]
            results += [RecognizerResult("PERSON", s, e, score) for s, e, score in _devanagari_people(text)]
            results += [
                RecognizerResult("PERSON", m.start(1), m.end(1), 0.9) for m in _HONORIFIC.finditer(text)
            ]
            return results

    import logging

    logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)  # its setup warnings carry no signal
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
    )
    registry = RecognizerRegistry(supported_languages=["en"])
    registry.add_recognizer(SpacyRecognizer(supported_entities=["PERSON"]))
    registry.add_recognizer(KfinNameRecognizer(supported_entities=["PERSON"], name="KfinNameRecognizer"))
    return AnalyzerEngine(nlp_engine=provider.create_engine(), registry=registry, supported_languages=["en"])


def warm_up() -> None:
    """Load the NER model at worker start rather than on the first submission."""
    _analyzer().analyze(text="Warm up", language="en")


def _people(text: str, never: set[str]) -> list[Found]:
    out = []
    for r in _analyzer().analyze(text=text, language="en", entities=["PERSON"], score_threshold=0.5):
        value = text[r.start : r.end].strip(" .,;:'’\"")
        words = value.split()
        while len(words) > 1 and words[0].casefold() in ROLE_WORDS:
            words = words[1:]  # "Customer Aditya Khan": keep the role word in the text, tag only the name
        value = " ".join(words) if len(words) < len(value.split()) else value
        if not value or value.casefold() in never or not any(ch.isalpha() for ch in value):
            continue
        if PLATFORM_ID.fullmatch(value):
            continue
        start = text.index(value, r.start)
        out.append(Found(start, start + len(value), "PERSON", value, priority=5))
    return out


# ---- detection ---------------------------------------------------------------------------------------------


def detect(
    text: str, d: Directory, *, kfin_domains: list[str] | None = None, people: bool = True
) -> list[Found]:
    """Every value to tag in `text`, non-overlapping, in text order."""
    domains = kfin_domains if kfin_domains is not None else get_settings().kfin_domains
    found: list[Found] = []
    for pm in scan(text, kfin_domains=domains):
        value = text[pm.start : pm.end]
        subject = d.employee_emails.get(value.lower()) if pm.pattern_id == "email" else None
        found.append(
            Found(pm.start, pm.end, PATTERN_TYPES.get(pm.pattern_id, "IDENTIFIER"), value, 1, subject)
        )
    for m in EMAIL_RE.finditer(text):  # any address, even one the pattern rules let through
        found.append(
            Found(m.start(), m.end(), "EMAIL", m.group(0), 1, d.employee_emails.get(m.group(0).lower()))
        )
    for m in CODE_RE.finditer(text):
        found.append(
            Found(
                m.start(),
                m.end(),
                "CONTRIBUTOR" if m.group(0).startswith("CTR") else "REVIEWER",
                m.group(0),
                2,
            )
        )
    if d._name_re is not None:
        for m in d._name_re.finditer(text):
            uid = d.employee_names.get(normalise_name(m.group(0)))
            found.append(Found(m.start(), m.end(), "KFIN_EMPLOYEE", m.group(0), 3, uid))
    for rx, typ in d._client_res:
        for m in rx.finditer(text):
            found.append(Found(m.start(), m.end(), typ, m.group(0), 4))
    if people and any(ch.isupper() for ch in text):
        found.extend(_people(text, d.never_person))
    elif people and _DEVA_WORD.search(text):
        # Hindi in Devanagari has no capital letters, so the gate above never opens for it (the review of BLD-C247):
        # the table alone, without the English NER model, which reads nothing in this script but noise.
        found.extend(_deva_found(text, d.never_person))

    chosen: list[Found] = []
    for f in sorted(found, key=lambda f: (f.priority, -(f.end - f.start), f.start)):
        if all(f.end <= c.start or f.start >= c.end for c in chosen):
            chosen.append(f)
    return sorted(chosen, key=lambda f: f.start)
