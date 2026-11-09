"""Words employees see (CLAUDE.md "Words on screen", DEC-035, DEC-038; brand pass review A5 and A7).

- One stage-word table: a stage reads the same for its owner as for everyone else.
- Find your crew is the only place a shipped idea reads "Already running" (BLD-104).
- No screen, email or match card says "Garage". The company-repo files that still mention it are internal notes
  (index pages and the compliance-tier rule) and no employee-facing view renders their text.
"""

from __future__ import annotations

from pathlib import Path

from comms.templates import render_text
from core.stage_words import MATCH_CARD_WORDS, PUBLIC_WORDS
from okf.frontmatter import parse
from views import mine
from views.wall import showcase

SEED = Path(__file__).resolve().parents[3] / "seed" / "company-repo"
NEVER = ("garage", "duplicate", "rejected", "already solved")

# Internal company-repo notes that still use the project's internal name. None of them is shown to employees:
# index pages are never indexed or rendered (index/indexer.py RESERVED), the showcase reads only SOL-*.md, and the
# compliance-tier rule is read as data by the rules engine.
INTERNAL_NOTES = {
    "index.md",
    "handovers/index.md",
    "rules/compliance-tier.md",
    "rules/index.md",
    "solutions/index.md",
}


def test_a_stage_reads_the_same_for_its_owner_and_for_everyone() -> None:
    for stage, word in PUBLIC_WORDS.items():
        assert mine.OWNER_WORDS[stage][0] == word, stage
    assert mine.OWNER_WORDS["closed"][0] == "Shipped"


def test_only_find_your_crew_says_already_running_for_a_shipped_idea() -> None:
    differs = {s for s in PUBLIC_WORDS if MATCH_CARD_WORDS[s] != PUBLIC_WORDS[s]}
    assert differs == {"shipped", "measuring", "closed"}
    assert {MATCH_CARD_WORDS[s] for s in differs} == {"Already running"}


def test_no_stage_word_uses_a_forbidden_word() -> None:
    words = [*PUBLIC_WORDS.values(), *MATCH_CARD_WORDS.values()]
    words += [w for pair in mine.OWNER_WORDS.values() for w in pair]
    for word in words:
        assert not any(bad in word.lower() for bad in NEVER), word


def test_only_internal_notes_in_the_company_repo_mention_garage() -> None:
    mentions = {
        str(p.relative_to(SEED))
        for p in SEED.rglob("*.md")
        if "garage" in p.read_text(encoding="utf-8").lower()
    }
    assert mentions <= INTERNAL_NOTES, sorted(mentions - INTERNAL_NOTES)


def test_message_templates_never_say_garage() -> None:
    for path in sorted((SEED / "comms" / "templates").glob("*.md")):
        if path.name == "index.md":
            continue
        doc = parse(path.read_text(encoding="utf-8"))
        meta = doc.meta or {}
        subject = str((meta.get("kfin") or {}).get("subject") or meta.get("title") or "")
        for text in (subject, doc.body):
            assert "garage" not in render_text(text, {}).lower(), path.name


def test_the_showcase_reads_only_solution_files() -> None:
    for card in showcase(SEED):
        assert card["solution_id"].startswith("SOL-")
        assert "garage" not in (card["title"] + card["description"]).lower()
