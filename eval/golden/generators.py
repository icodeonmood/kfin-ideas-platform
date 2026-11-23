"""Placeholder generators for synthetic test data (see generators.md).

Values are generated at run time from a fixed seed (`GOLDEN_SEED`, default 42) and never stored in the repo.
Each generator takes a `random.Random`, so a test controls its own sequence.
"""

from __future__ import annotations

import os
import random
import re
from collections.abc import Callable, Sequence

_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# Common given names and surnames, combined at random; no entry is a public figure.
_FIRST = (
    "Aarav", "Ananya", "Vihaan", "Diya", "Ishaan", "Meera", "Kabir", "Saanvi", "Arjun", "Riya",
    "Rohan", "Kavya", "Aditya", "Nisha", "Siddharth", "Pooja", "Karthik", "Lakshmi", "Manoj", "Sneha",
    "Farhan", "Zoya", "Harpreet", "Gurleen", "Tenzin", "Anjali", "Pranav", "Divya", "Naveen", "Shreya",
)
_LAST = (
    "Sharma", "Iyer", "Reddy", "Nair", "Patel", "Gupta", "Menon", "Rao", "Das", "Singh",
    "Joshi", "Kulkarni", "Banerjee", "Chatterjee", "Pillai", "Verma", "Mehta", "Shah", "Khan", "Bhat",
)
_LOCALITIES = ("Banjara Hills", "Gachibowli", "Malviya Nagar", "Koramangala", "Andheri East", "Salt Lake")
_STREETS = ("MG Road", "Station Road", "Temple Street", "Lake View Road", "Park Avenue", "Ring Road")


def default_rng(offset: int = 0) -> random.Random:
    return random.Random(int(os.environ.get("GOLDEN_SEED", "42")) + offset)


def verhoeff_check_digit(digits: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(ch)]]
    return str(_VERHOEFF_INV[c])


def luhn_check_digit(digits: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return str((10 - total % 10) % 10)


def _digits(rng: random.Random, n: int, first: str = "0123456789") -> str:
    return rng.choice(first) + "".join(rng.choice("0123456789") for _ in range(n - 1))


def pan(rng: random.Random) -> str:
    return "".join(rng.choice(_LETTERS) for _ in range(3)) + "P" + rng.choice(_LETTERS) + _digits(rng, 4) + rng.choice(_LETTERS)


def aadhaar(rng: random.Random) -> str:
    body = _digits(rng, 11, "23456789")
    full = body + verhoeff_check_digit(body)
    sep = rng.choice(("", " ", "-"))
    return sep.join((full[:4], full[4:8], full[8:]))


def aadhaar_masked(rng: random.Random) -> str:
    return "XXXX XXXX " + _digits(rng, 4)


def mobile(rng: random.Random) -> str:
    number = _digits(rng, 10, "6789")
    prefix = rng.choice(("", "+91 ", "+91", "0"))
    middle = rng.choice(("", " "))
    return prefix + number[:5] + middle + number[5:]


def ext_email(rng: random.Random) -> str:
    local = rng.choice(_FIRST).lower() + "." + rng.choice(_LAST).lower() + str(rng.randint(1, 99))
    return f"{local}@{rng.choice(('example.com', 'example.in'))}"


def kfin_email(rng: random.Random, domains: Sequence[str] | None = None) -> str:
    domain_list = list(domains) if domains else os.environ.get("KFIN_EMAIL_DOMAINS", "kfintech.com").split(",")
    local = rng.choice(_FIRST).lower() + "." + rng.choice(_LAST).lower()
    return f"{local}@{domain_list[0].strip()}"


def account(rng: random.Random) -> str:
    return _digits(rng, rng.randint(9, 18), "123456789")


def card(rng: random.Random) -> str:
    body = "400000" + _digits(rng, 9)  # test-range prefix
    full = body + luhn_check_digit(body)
    return " ".join(full[i : i + 4] for i in range(0, 16, 4))


def folio(rng: random.Random) -> str:
    base = _digits(rng, rng.randint(6, 12), "123456789")
    return base + (f"/{rng.randint(1, 99):02d}" if rng.random() < 0.3 else "")


def demat(rng: random.Random) -> str:
    return "IN" + _digits(rng, 14) if rng.random() < 0.5 else _digits(rng, 16, "123456789")


def pran(rng: random.Random) -> str:
    return _digits(rng, 12, "123456789")


def dob(rng: random.Random) -> str:
    y, m, d = rng.randint(1940, 2005), rng.randint(1, 12), rng.randint(1, 28)
    style = rng.randint(0, 2)
    if style == 0:
        return f"{d:02d}/{m:02d}/{y}"
    if style == 1:
        return f"{d:02d}-{_MONTHS[m - 1]}-{y}"
    return f"{y}-{m:02d}-{d:02d}"


def ifsc(rng: random.Random) -> str:
    return "".join(rng.choice(_LETTERS) for _ in range(4)) + "0" + "".join(rng.choice(_LETTERS + "0123456789") for _ in range(6))


def arn(rng: random.Random) -> str:
    return "ARN-" + _digits(rng, rng.randint(4, 6), "123456789")


def euin(rng: random.Random) -> str:
    return "E" + _digits(rng, 6)


def person_name(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"


def address(rng: random.Random) -> str:
    return (
        f"Flat {rng.randint(101, 1204)}, {rng.choice(_LAST)} Residency, "
        f"{rng.choice(_STREETS)}, {rng.choice(_LOCALITIES)}"
    )


def last4(rng: random.Random) -> str:
    return _digits(rng, 4)


GENERATORS: dict[str, Callable[[random.Random], str]] = {
    "PAN": pan,
    "AADHAAR": aadhaar,
    "AADHAAR_MASKED": aadhaar_masked,
    "MOBILE": mobile,
    "EXT_EMAIL": ext_email,
    "KFIN_EMAIL": kfin_email,
    "ACCOUNT": account,
    "CARD": card,
    "FOLIO": folio,
    "DEMAT": demat,
    "PRAN": pran,
    "DOB": dob,
    "IFSC": ifsc,
    "ARN": arn,
    "EUIN": euin,
    "PERSON_NAME": person_name,
    "ADDRESS": address,
    "LAST4": last4,
}

# Placeholders that need run-time context rather than a generator.
CONTEXT_PLACEHOLDERS = frozenset({"COLLEAGUE_NAME", "CLIENT_AMC_NAME", "ACCOUNT_IN_WORDS"})

_PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def placeholders(text: str) -> set[str]:
    return set(_PLACEHOLDER.findall(text))


def fill(text: str, rng: random.Random, context: dict[str, Callable[[random.Random], str]] | None = None) -> str:
    """Replace every {{PLACEHOLDER}} with a generated value. Unknown placeholders raise KeyError."""
    extra = context or {}

    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in extra:
            return extra[key](rng)
        return GENERATORS[key](rng)

    return _PLACEHOLDER.sub(sub, text)
