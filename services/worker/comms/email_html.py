"""Branded HTML email (DEC-061, BLD-125). Every template keeps its wording; only the rendering changes.

One HTML document per message, built from tables 600 px wide with inline styles and one style block:

- light colours inline, which is what Outlook desktop shows;
- a dark version through `prefers-color-scheme`, plus the `[data-ogsc]`/`[data-ogsb]` selectors Outlook.com
  uses when it darkens a message;
- a Zed header band with the Spark mark as a hosted PNG (never SVG: most mail apps drop it), Arial throughout,
  one bulletproof Electric button, and the footer lines "1% spark. 99% sweat." and "A KFintech programme".

Template values never become markup: the template is first rendered with a placeholder for each value, the
small Markdown subset the templates use (paragraphs, `**bold**`, `[label](url)`, `- ` lists, `## ` headings) is
turned into HTML, and only then is each value put back, escaped. A link only keeps an http(s) or app-relative
address. The plain-text part is the template's own text with the Markdown marks taken out.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Literal

from comms.templates import Template, _lookup, render_text
from ones.tiers import TIERS

Theme = Literal["auto", "light", "dark"]

TAGLINE = "1% spark. 99% sweat."
ENDORSEMENT = "A KFintech programme"
FONT = "Arial, Helvetica, sans-serif"
MARK_FILE = "brand/email-mark-white@2x.png"  # 40 x 48, shown at 20 x 24

# The two palettes. Light is inline (Outlook desktop); dark arrives through the style block, or inline for
# previews and snapshots. Pairs used for text meet WCAG AA: Ink on white 19.7:1, Slate on white 6.1:1, white on
# Graphite 17.6:1, Ash on Graphite 6.9:1, the dark-mode link blue on Graphite 6.7:1, white on Electric 5.2:1.
PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "page": "#F3F4F6",
        "card": "#FFFFFF",
        "text": "#0A0A0C",
        "muted": "#5C6270",
        "panel": "#F3F4F6",
        "line": "#DCDFE5",
        "link": "#2B5BFF",
    },
    "dark": {
        "page": "#0A0A0C",
        "card": "#17181C",
        "text": "#FFFFFF",
        "muted": "#9EA3AD",
        "panel": "#0A0A0C",
        "line": "#2A2C33",
        "link": "#7C9BFF",
    },
}
ZED = "#0A0A0C"
WHITE = "#FFFFFF"
ELECTRIC = "#2B5BFF"
ASH = "#9EA3AD"

_TOKEN = re.compile(r"\{\{#([a-z_.0-9]+)\}\}(.*?)\{\{/\1\}\}|\{\{([a-z_.0-9]+)\}\}", re.S)
_SLOT = re.compile("(\\d+)")
_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_LINK_ONLY = re.compile(r"^\[([^\]\n]+)\]\(([^)\s]+)\)$")


@dataclass(frozen=True)
class Email:
    subject: str
    text: str
    html: str


def _render_slots(text: str, data: dict[str, Any], values: list[str]) -> str:
    """Like `render_text`, but each value becomes a placeholder; the values are kept in order in `values`."""

    def token(m: re.Match[str]) -> str:
        if m.group(1) is not None:
            return _render_slots(m.group(2), data, values) if _lookup(data, m.group(1)) else ""
        v = _lookup(data, m.group(3))
        values.append("" if v is None else str(v))
        return f"{len(values) - 1}"

    return _TOKEN.sub(token, text)


def _fill(escaped: str, values: list[str]) -> str:
    return _SLOT.sub(lambda m: html.escape(values[int(m.group(1))]), escaped)


def _plain(fragment: str, values: list[str]) -> str:
    return _SLOT.sub(lambda m: values[int(m.group(1))], fragment)


def _safe_url(raw: str, values: list[str], base: str) -> str | None:
    url = _plain(raw, values).strip()
    if url.startswith("/"):
        url = base.rstrip("/") + url
    return url if re.match(r"^https?://", url, re.I) else None


def _inline(fragment: str, values: list[str], base: str, colours: dict[str, str]) -> str:
    """Escape a run of text, then apply bold and links; values are filled in last, escaped."""
    out = html.escape(fragment, quote=False)

    def link(m: re.Match[str]) -> str:
        url = _safe_url(m.group(2), values, base)
        label = m.group(1)
        if not url:
            return label
        return (
            f'<a class="em-link" href="{html.escape(url, quote=True)}" '
            f'style="color:{colours["link"]};text-decoration:underline;">{label}</a>'
        )

    out = _LINK.sub(link, out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    return _fill(out, values).replace("\n", "<br>")


def _button(label: str, url: str) -> str:
    """A bulletproof button: the cell carries the colour, so Outlook desktop shows it without CSS support."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 20px;">'
        f'<tr><td bgcolor="{ELECTRIC}" style="border-radius:10px;background:{ELECTRIC};">'
        f'<a href="{html.escape(url, quote=True)}" style="display:inline-block;padding:13px 22px;'
        f"font-family:{FONT};font-size:16px;font-weight:bold;line-height:20px;color:{WHITE};"
        f'text-decoration:none;border-radius:10px;">{label}</a></td></tr></table>'
    )


def _blocks(body: str, values: list[str], base: str, colours: dict[str, str]) -> list[str]:
    out: list[str] = []
    button_done = False
    p_style = f"margin:0 0 16px;font-family:{FONT};font-size:16px;line-height:24px;color:{colours['text']};"
    for para in re.split(r"\n\s*\n", body.strip()):
        para = para.strip()
        if not para:
            continue
        plain = _plain(para, values).strip()
        if plain in (TAGLINE, ENDORSEMENT):
            continue  # both lines live in the footer
        m = _LINK_ONLY.match(para)
        if m:
            url = _safe_url(m.group(2), values, base)
            label = _fill(html.escape(m.group(1), quote=False), values)
            if url and not button_done:
                out.append(_button(label, url))
                button_done = True
            elif url:
                out.append(
                    f'<p class="em-text" style="{p_style}"><a class="em-link" href="{html.escape(url, quote=True)}" '
                    f'style="color:{colours["link"]};text-decoration:underline;">{label}</a></p>'
                )
            else:  # an address we won't link to: keep the words, drop the link
                out.append(f'<p class="em-text" style="{p_style}">{label}</p>')
            continue
        if para.startswith("## "):
            out.append(
                f'<h2 class="em-text" style="margin:8px 0 12px;font-family:{FONT};font-size:19px;line-height:26px;'
                f'font-weight:bold;color:{colours["text"]};">{_inline(para[3:], values, base, colours)}</h2>'
            )
            continue
        lines = para.split("\n")
        if all(ln.lstrip().startswith("- ") for ln in lines):
            items = "".join(
                f'<li style="margin:0 0 6px;">{_inline(ln.lstrip()[2:], values, base, colours)}</li>'
                for ln in lines
            )
            out.append(
                f'<ul class="em-text" style="margin:0 0 16px;padding-left:22px;font-family:{FONT};font-size:16px;'
                f'line-height:24px;color:{colours["text"]};">{items}</ul>'
            )
            continue
        out.append(f'<p class="em-text" style="{p_style}">{_inline(para, values, base, colours)}</p>')
    return out


def _one_number(data: dict[str, Any]) -> tuple[Any, Any] | None:
    """(number, tier) when this message shows the recipient their own number, else None."""
    one = data.get("one") or {}
    number = one.get("number")
    if number in (None, "") or not one.get("show_number"):
        return None
    return number, (data.get("tier") or {}).get("to") or one.get("tier")  # a tier change shows the new tier


def _one_block(data: dict[str, Any]) -> str:
    shown = _one_number(data)
    if shown is None:
        return ""
    number, tier = shown
    tier_row = ""
    if isinstance(tier, int) and tier in TIERS:
        name, colour = TIERS[tier]
        tier_row = (
            f'<tr><td style="padding:10px 0 0;font-family:{FONT};font-size:14px;line-height:20px;color:{ASH};">'
            f'<span style="display:inline-block;width:12px;height:12px;border-radius:6px;background:{colour};'
            f'vertical-align:-1px;margin-right:8px;"></span>Tier {tier}, {html.escape(name)}</td></tr>'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:0 0 20px;"><tr><td bgcolor="{ZED}" style="background:{ZED};border-radius:12px;'
        'padding:18px 20px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="font-family:{FONT};font-size:13px;line-height:18px;color:{ASH};">Your number</td></tr>'
        f'<tr><td style="font-family:{FONT};font-size:40px;line-height:44px;font-weight:bold;color:{WHITE};">'
        f"No. {html.escape(str(number))}</td></tr>{tier_row}</table></td></tr></table>"
    )


def _card_line(data: dict[str, Any], rendered_body: str) -> str:
    line = str((data.get("idea") or {}).get("one_line") or "").strip()
    return "" if not line or line in rendered_body else line


def _idea_card(data: dict[str, Any], rendered_body: str, colours: dict[str, str]) -> str:
    """The idea in a card, unless the message already quotes it."""
    line = _card_line(data, rendered_body)
    if not line:
        return ""
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 20px;">'
        f'<tr><td class="em-panel em-line" style="background:{colours["panel"]};border:1px solid {colours["line"]};'
        'border-radius:12px;padding:16px 18px;">'
        f'<p class="em-muted" style="margin:0 0 6px;font-family:{FONT};font-size:13px;line-height:18px;'
        f'color:{colours["muted"]};">Idea</p>'
        f'<p class="em-text" style="margin:0;font-family:{FONT};font-size:16px;line-height:23px;font-weight:bold;'
        f'color:{colours["text"]};">{html.escape(line)}</p></td></tr></table>'
    )


_DARK_CSS = (
    "@media (prefers-color-scheme: dark) {"
    " .em-page { background:#0A0A0C !important; }"
    " .em-card { background:#17181C !important; }"
    " .em-text { color:#FFFFFF !important; }"
    " .em-muted { color:#9EA3AD !important; }"
    " .em-panel { background:#0A0A0C !important; }"
    " .em-line { border-color:#2A2C33 !important; }"
    " .em-link { color:#7C9BFF !important; }"
    " }"
    " [data-ogsb] .em-page { background-color:#0A0A0C !important; }"
    " [data-ogsb] .em-card { background-color:#17181C !important; }"
    " [data-ogsb] .em-panel { background-color:#0A0A0C !important; }"
    " [data-ogsc] .em-text { color:#FFFFFF !important; }"
    " [data-ogsc] .em-muted { color:#9EA3AD !important; }"
    " [data-ogsc] .em-link { color:#7C9BFF !important; }"
)


def shell(subject: str, inner: list[str], base: str, theme: Theme = "auto") -> str:
    """The page around a message: header band, the card with a hero line, and the footer."""
    colours = PALETTES["dark" if theme == "dark" else "light"]
    mark = f"{base.rstrip('/')}/{MARK_FILE}"
    style = "" if theme != "auto" else f"<style>{_DARK_CSS}</style>"
    scheme = {"auto": "light dark", "light": "light", "dark": "dark"}[theme]
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<meta name="color-scheme" content="{scheme}"><meta name="supported-color-schemes" content="{scheme}">'
        f"<title>{html.escape(subject)}</title>{style}</head>"
        f'<body class="em-page" style="margin:0;padding:0;background:{colours["page"]};">'
        '<table role="presentation" class="em-page" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{colours["page"]};"><tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;max-width:600px;">'
        # Header band: always Zed, so the white mark and name read in both themes.
        f'<tr><td bgcolor="{ZED}" style="background:{ZED};border-radius:12px 12px 0 0;padding:16px 28px;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="padding-right:10px;"><img src="{html.escape(mark, quote=True)}" width="20" height="24" '
        'alt="" style="display:block;border:0;"></td>'
        f'<td style="font-family:{FONT};font-size:18px;line-height:24px;font-weight:bold;color:{WHITE};">'
        "1% Club</td></tr></table></td></tr>"
        f'<tr><td class="em-card" style="background:{colours["card"]};padding:28px 28px 12px;">'
        f'<h1 class="em-text" style="margin:0 0 20px;font-family:{FONT};font-size:26px;line-height:32px;'
        f'font-weight:bold;color:{colours["text"]};">{html.escape(subject)}</h1>'
        + "".join(inner)
        + "</td></tr>"
        f'<tr><td class="em-card em-line" style="background:{colours["card"]};border-top:1px solid '
        f'{colours["line"]};border-radius:0 0 12px 12px;padding:16px 28px 22px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td class="em-text" style="font-family:{FONT};font-size:13px;line-height:18px;font-weight:bold;'
        f'color:{colours["text"]};">{TAGLINE}</td>'
        f'<td class="em-muted" align="right" style="font-family:{FONT};font-size:13px;line-height:18px;'
        f'color:{colours["muted"]};">{ENDORSEMENT}</td></tr></table></td></tr>'
        "</table></td></tr></table></body></html>"
    )


def to_text(body: str) -> str:
    """The plain-text part: the rendered template with its Markdown marks taken out."""
    text = _LINK.sub(lambda m: f"{m.group(1)}: {m.group(2)}", body)
    text = text.replace("**", "")
    text = re.sub(r"^## ", "", text, flags=re.M)
    return text.strip() + "\n"


def message_body(tpl: Template, data: dict[str, Any], base: str, theme: Theme = "auto") -> list[str]:
    """The blocks of one message: the One's number, the idea card and the body."""
    colours = PALETTES["dark" if theme == "dark" else "light"]
    values: list[str] = []
    slotted = _render_slots(tpl.body, data, values)
    rendered = render_text(tpl.body, data)
    return [_one_block(data), _idea_card(data, rendered, colours), *_blocks(slotted, values, base, colours)]


def text_part(tpl: Template, data: dict[str, Any]) -> str:
    """The plain-text part with the same blocks as the HTML: the One's number and the idea card first."""
    rendered = render_text(tpl.body, data)
    head: list[str] = []
    shown = _one_number(data)
    if shown is not None:
        number, tier = shown
        words = f"Tier {tier}, {TIERS[tier][0]}" if isinstance(tier, int) and tier in TIERS else ""
        head.append(f"Your number: No. {number}" + (f" ({words})" if words else ""))
    line = _card_line(data, rendered)
    if line:
        head.append(f"Idea: {line}")
    return ("\n".join(head) + "\n\n" if head else "") + to_text(rendered)


def compose(tpl: Template, data: dict[str, Any], base: str, theme: Theme = "auto") -> Email:
    subject = render_text(tpl.subject, data).strip()
    return Email(
        subject, text_part(tpl, data), shell(subject, message_body(tpl, data, base, theme), base, theme)
    )


def digest(sections: list[tuple[Template, dict[str, Any]]], base: str, theme: Theme = "auto") -> Email:
    """Several held messages in one email: each keeps its subject as a heading."""
    colours = PALETTES["dark" if theme == "dark" else "light"]
    subject = f"Your 1% Club update: {len(sections)} new"
    inner: list[str] = []
    texts: list[str] = []
    for tpl, data in sections:
        s = render_text(tpl.subject, data).strip()
        inner.append(
            f'<h2 class="em-text" style="margin:12px 0 12px;font-family:{FONT};font-size:19px;line-height:26px;'
            f'font-weight:bold;color:{colours["text"]};">{html.escape(s)}</h2>'
        )
        inner.extend(message_body(tpl, data, base, theme))
        texts.append(f"{s}\n\n{text_part(tpl, data)}")
    return Email(subject, "\n\n".join(texts), shell(subject, inner, base, theme))
