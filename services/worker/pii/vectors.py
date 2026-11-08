"""Shared test vectors for the level-1 personal-data check (AT-B3-03, BLD-005).

Generated at run time from eval/golden/generators.py (never stored): every pattern in several variants, the
allowed forms (masked Aadhaar, KFin email warns only) and near misses that must not block. Each vector carries
what it must do (`expect`) and exactly what the Python engine found (`python`), so the TypeScript engine is held
to the same answer, span for span.

python -m pii.vectors [--n 20]   prints the vectors as JSON
"""

from __future__ import annotations

import argparse
import importlib
import json
import random
import sys
from collections.abc import Callable
from typing import Any

from core.config import REPO_ROOT, get_settings
from pii.patterns import scan

sys.path.insert(0, str(REPO_ROOT / "eval" / "golden")) if REPO_ROOT else None
g = importlib.import_module("generators")

Gen = Callable[[random.Random], str]


def _euin(rng: random.Random) -> str:
    return "E" + "".join(rng.choice("0123456789") for _ in range(6))


# (vector id, text template, generator, expected: (pattern ids any-of, action) or None for "no block, no warn")
CASES: list[tuple[str, str, Gen, tuple[tuple[str, ...], str] | None]] = [
    ("pan", "Investor PAN {v} called about a stuck redemption", g.pan, (("pan",), "block")),
    ("aadhaar", "The form had Aadhaar {v} written in the remarks box", g.aadhaar, (("aadhaar",), "block")),
    ("aadhaar_masked", "Aadhaar {v} is masked, which is allowed", g.aadhaar_masked, None),
    ("mobile", "Investor asked us to call back on {v} today", g.mobile, (("mobile",), "block")),
    ("email_external", "The distributor mailed {v} with the form", g.ext_email, (("email",), "block")),
    (
        "bank_account",
        "Redemption bounced because a/c {v} was closed",
        g.account,
        (("bank_account",), "block"),
    ),
    ("card", "Card {v} was declined at the counter", g.card, (("card",), "block")),
    ("folio", "Folio {v} has a stuck SIP", g.folio, (("folio",), "block")),
    ("demat", "Demat account {v} is frozen", g.demat, (("demat_in", "demat_16"), "block")),
    ("pran", "PRAN {v} was not updated in the CRA", g.pran, (("pran",), "block")),
    ("dob", "DOB {v} did not match the KYC record", g.dob, (("dob",), "block")),
    ("ifsc_alone", "The branch IFSC {v} changed after the merger", g.ifsc, (("ifsc",), "warn")),
    ("arn", "Distributor {v} asked for a commission statement", g.arn, (("arn",), "warn")),
    ("euin", "The EUIN {v} was missing on the form", _euin, (("euin",), "warn")),
]

NEAR_MISSES = [
    "We processed {n} units last year across all schemes",
    "Scheme code {s} and ISIN INF200K01RJ1 are fine",
    "The cut-off is 15/03/2026 for this quarter",
    "Invoice {s} from the vendor was paid late",
    "About {n} SIP registrations a month go NIGO",
    "Version 2.4.1 of the app shipped on 2026-11-02",
]


def build(n: int = 20, seed: int | None = None) -> dict[str, Any]:
    rng = g.default_rng(0) if seed is None else random.Random(seed)
    domains = get_settings().kfin_domains
    vectors: list[dict[str, Any]] = []

    def add(vid: str, text: str, expect: dict[str, Any]) -> None:
        found = scan(text, kfin_domains=domains)
        vectors.append(
            {
                "id": vid,
                "text": text,
                "expect": expect,
                "python": [
                    {"pattern": m.pattern_id, "action": m.action, "start": m.start, "end": m.end}
                    for m in found
                ],
            }
        )

    for vid, template, gen, expectation in CASES:
        for i in range(n):
            text = template.format(v=gen(rng))
            if expectation is None:
                add(f"{vid}-{i}", text, {"blocks": False, "warns": False, "patterns": []})
            else:
                patterns, action = expectation
                add(
                    f"{vid}-{i}",
                    text,
                    {"blocks": action == "block", "warns": action == "warn", "patterns": list(patterns)},
                )
    for i in range(n):
        kfin = g.kfin_email(rng, domains)
        add(
            f"email_kfin-{i}",
            f"Please write to {kfin} for the file",
            {"blocks": False, "warns": True, "patterns": ["email"]},
        )
        add(
            f"ifsc_with_account-{i}",
            f"Credit a/c {g.account(rng)} at IFSC {g.ifsc(rng)} for the refund",
            {"blocks": True, "warns": False, "patterns": ["bank_account", "ifsc"]},
        )
    for i, template in enumerate(NEAR_MISSES * max(1, n // len(NEAR_MISSES))):
        text = template.format(n=rng.randint(1_000_000_000, 5_999_999_999), s=rng.randint(100_000, 999_999))
        add(f"near_miss-{i}", text, {"blocks": False, "warns": False, "patterns": []})
    return {"kfin_domains": domains, "count": len(vectors), "vectors": vectors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args(argv)
    json.dump(build(args.n), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
