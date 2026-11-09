"""The Ember as an email (BLD-128): the sent issue, in the brand's HTML shell (BLD-125) and as plain text. Every value
is escaped; the issue holds only what everyone may already see."""

from __future__ import annotations

import html
from typing import Any

from comms.email_html import FONT, PALETTES, Email, Theme, shell

UNITS_ORDER = ("time", "money", "effort", "scale")
UNIT_WORDS = {"time": "Time", "money": "Money", "effort": "Effort", "scale": "Scale"}


def grouped(value: float) -> str:
    """Indian digit grouping (12,34,567.5), as `Intl.NumberFormat("en-IN")` shows it on the web."""
    v = float(value)
    whole, _, frac = f"{abs(v):.3f}".rstrip("0").rstrip(".").partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ("-" if v < 0 else "") + ",".join([*groups, tail]) + (f".{frac}" if frac else "")


def measure_words(key: str, m: dict[str, Any]) -> str:
    """The same words as `measureText` in apps/web/src/lib/measures.ts (Ember review)."""
    value, unit = grouped(m["value"]), str(m.get("unit") or "")
    if key == "money":
        unit = unit.removeprefix("rupees ").removeprefix("rupees")
        return f"₹{value} {unit}".strip()
    if key == "time":
        return f"{value} {unit} given back".replace("  ", " ")
    return f"{value} {unit}".strip()


def _measures_text(measures: dict[str, Any]) -> str:
    parts = []
    for key in UNITS_ORDER:
        m = measures.get(key)
        if m and m.get("value") is not None:
            parts.append(f"{UNIT_WORDS[key]}: {measure_words(key, m)}")
    return ". ".join(parts)


def _one_name(o: dict[str, Any]) -> str:
    return f"No. {o['number']}, {o['name']}" if o.get("name") else f"One No. {o['number']}"


def _h2(text: str, c: dict[str, str]) -> str:
    return (
        f'<h2 class="em-text" style="margin:24px 0 10px;font-family:{FONT};font-size:20px;line-height:26px;'
        f'font-weight:bold;color:{c["text"]};">{html.escape(text)}</h2>'
    )


def _p(text: str, c: dict[str, str], *, muted: bool = False, bold: bool = False) -> str:
    cls, colour = ("em-muted", c["muted"]) if muted else ("em-text", c["text"])
    weight = "bold" if bold else "normal"
    return (
        f'<p class="{cls}" style="margin:0 0 12px;font-family:{FONT};font-size:16px;line-height:24px;'
        f'font-weight:{weight};color:{colour};">{html.escape(text)}</p>'
    )


def _item(title: str, lines: list[str], c: dict[str, str]) -> str:
    body = "".join(
        f'<p class="em-muted" style="margin:4px 0 0;font-family:{FONT};font-size:14px;line-height:20px;'
        f'color:{c["muted"]};">{html.escape(ln)}</p>'
        for ln in lines
        if ln
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 10px;">'
        f'<tr><td class="em-panel em-line" style="background:{c["panel"]};border:1px solid {c["line"]};'
        'border-radius:12px;padding:14px 16px;">'
        f'<p class="em-text" style="margin:0;font-family:{FONT};font-size:16px;line-height:22px;font-weight:bold;'
        f'color:{c["text"]};">{html.escape(title)}</p>{body}</td></tr></table>'
    )


def sections(issue: dict[str, Any]) -> list[tuple[str, list[tuple[str, list[str]]], str | None]]:
    """(heading, items as (title, lines), a line when the section is empty) in the order The Ember reads."""
    impact = [
        (_one_name(o), [o.get("line") or "", _measures_text(o.get("measures") or {})])
        for o in issue["impact"]
    ]
    new_ones = [
        (
            _one_name(o) + (", founding One" if o.get("founding") else ""),
            [o.get("brief") or o.get("line") or ""],
        )
        for o in issue["new_ones"]
    ]
    shipped = [(s["label"], [s["words"]]) for s in issue["shipped"]]
    shipped += [
        (r["label"], [f"Measured at {r['mark']}: " + _measures_text(r["measures"])]) for r in issue["results"]
    ]
    by_lob = [
        (r["lob"], [f"Shared this month: {r['shared']}. Picked so far: {r['picked']}."])
        for r in issue["by_lob"]
    ]
    return [
        ("Impact created by Ones", impact, "Results arrive 30 and 90 days after something ships."),
        ("New Ones", new_ones, "No new Ones this month."),
        ("Shipped, with results", shipped, "Nothing shipped this month."),
        ("Ideas in and picked", by_lob, "No ideas shared this month."),
    ]


def compose(issue: dict[str, Any], base: str, link: str, theme: Theme = "auto") -> Email:
    c = PALETTES["dark" if theme == "dark" else "light"]
    subject = f"The Ember, {issue['month_label']}"
    inner = [_p("What is glowing at the 1% Club this month.", c, muted=True)]
    text = [f"{subject}\n\nWhat is glowing at the 1% Club this month."]
    for heading, items, empty in sections(issue):
        inner.append(_h2(heading, c))
        text.append(heading)
        if not items:
            inner.append(_p(empty or "", c, muted=True))
            text.append(empty or "")
        for title, lines in items:
            inner.append(_item(title, lines, c))
            text.append("\n".join([title, *[ln for ln in lines if ln]]))
    inner.append(_h2("What the committee looks for", c))
    inner.append(_p(issue.get("note") or "", c))
    inner.append(_p("Chair, 1% Club core committee", c, muted=True))
    text += ["What the committee looks for", issue.get("note") or "", "Chair, 1% Club core committee"]
    if issue.get("managers"):
        inner.append(_h2("Thank you, managers", c))
        names = ", ".join(issue["managers"])
        inner.append(_p(f"Their teams shared the most this month: {names}.", c))
        text += ["Thank you, managers", f"Their teams shared the most this month: {names}."]
    inner.append(
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:16px 0 20px;">'
        '<tr><td bgcolor="#2B5BFF" style="border-radius:10px;background:#2B5BFF;">'
        f'<a href="{html.escape(link, quote=True)}" style="display:inline-block;padding:13px 22px;font-family:{FONT};'
        'font-size:16px;font-weight:bold;line-height:20px;color:#FFFFFF;text-decoration:none;border-radius:10px;">'
        "Read it in the app</a></td></tr></table>"
    )
    text += [f"Read it in the app: {link}", "1% spark. 99% sweat.", "A KFintech programme"]
    return Email(
        subject, "\n\n".join(t for t in text if t is not None) + "\n", shell(subject, inner, base, theme)
    )
