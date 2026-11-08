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


_cache: dict[str, tuple[float, Directory]] = {}
_cache_lock = threading.Lock()


def directory(conn: Conn, repo: Path | None = None) -> Directory:
    """The directory, rebuilt at most once a minute per database and repo."""
    key = f"{conn.info.dsn}|{repo or get_settings().company_repo_path}"
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < DIRECTORY_TTL_S:
            return hit[1]
    d = build_directory(conn, repo)
    with _cache_lock:
        _cache[key] = (time.monotonic(), d)
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
            results += [
                RecognizerResult("PERSON", m.start(1), m.end(1), 0.9) for m in _HONORIFIC.finditer(text)
            ]
            return results

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

    chosen: list[Found] = []
    for f in sorted(found, key=lambda f: (f.priority, -(f.end - f.start), f.start)):
        if all(f.end <= c.start or f.start >= c.end for c in chosen):
            chosen.append(f)
    return sorted(chosen, key=lambda f: f.start)
