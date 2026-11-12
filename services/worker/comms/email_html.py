"""Branded HTML email (DEC-061, BLD-125). Every template keeps its wording; only the rendering changes.

One HTML document per message, built from tables 600 px wide with inline styles and one style block:

- light colours inline, which is what Outlook desktop shows;
- a dark version through `prefers-color-scheme`, plus the `[data-ogsc]`/`[data-ogsb]` selectors Outlook.com
  uses when it darkens a message;
- OFFER's look (DEC-101, values from lane D's boards): ink on a warm paper ground, a white card with a hairline
  border, an ink header with the Spark mark as a hosted PNG (never SVG: most mail apps drop it), one bulletproof
  black button, ink links (standalone ones end in an arrow), the One's number on a dark panel with the tier as a
  filled dash, and a footer band with "1% Club", "1% spark. 99% sweat." and "A KFintech programme";
- Inter where the mail app has it, else Arial (no web fonts are loaded).

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
FONT = "Inter, Arial, Helvetica, sans-serif"
HEAD_FONT = "'Inter Tight', Inter, Arial, sans-serif"
MARK_FILE = "brand/email-mark-ink@2x.png"  # 44 x 53, shown at 22 x 26, on paper
MARK_FILE_DARK = "brand/email-mark-white@2x.png"  # the same mark for mail apps in dark mode

# The two palettes (OFFER, DEC-101). Light is inline (Outlook desktop); dark arrives through the style block, or
# inline for previews and snapshots. Text pairs meet WCAG AA (tests/test_email_html.py computes them): ink on
# white 18.9:1 and on paper 16.9:1; muted on white 6.4:1, on paper 5.7:1 and on the footer band 5.2:1; white on
# the dark card 17.4:1; muted on the dark card 6.9:1 and on the One's panel 7.5:1; the button 18.9:1 both ways.
PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "page": "#F3F3F1",
        "card": "#FFFFFF",
        "border": "#E4E4E0",
        "text": "#111111",
        "muted": "#5F5F64",
        "panel": "#F3F3F1",
        "line": "#EDEDEA",
        "link": "#111111",
        "button": "#111111",
        "button_text": "#FFFFFF",
        "foot": "#E9E9E6",
        "foot_line": "#DADAD6",
    },
    "dark": {
        "page": "#111111",
        "card": "#1A1A1E",
        "border": "#2C2C30",
        "text": "#FFFFFF",
        "muted": "#A3A3A6",
        "panel": "#111111",
        "line": "#2C2C30",
        "link": "#FFFFFF",
        "button": "#FFFFFF",
        "button_text": "#111111",
        "foot": "#161619",
        "foot_line": "#2C2C30",
    },
}
INK = "#111111"  # the One's panel, dark in both themes
WHITE = "#FFFFFF"
PANEL_MUTED = "#A3A3A6"

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
        )  # inline links: ink, underlined (DEC-101)

    out = _LINK.sub(link, out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    return _fill(out, values).replace("\n", "<br>")


def _button(label: str, url: str, colours: dict[str, str]) -> str:
    """A bulletproof black button (DEC-101): the cell carries the colour, so Outlook desktop shows it without CSS
    support. Mail apps in dark mode turn it white with ink words."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 24px;">'
        f'<tr><td class="em-btn-cell" bgcolor="{colours["button"]}" '
        f'style="border-radius:10px;background:{colours["button"]};">'
        f'<a class="em-btn" href="{html.escape(url, quote=True)}" style="display:inline-block;padding:14px 22px;'
        f"font-family:{FONT};font-size:16px;font-weight:600;line-height:20px;color:{colours['button_text']};"
        f'text-decoration:none;border-radius:10px;">{label}</a></td></tr></table>'
    )


def _blocks(body: str, values: list[str], base: str, colours: dict[str, str]) -> list[str]:
    out: list[str] = []
    button_done = False
    p_style = f"margin:0 0 16px;font-family:{FONT};font-size:16px;line-height:26px;color:{colours['text']};"
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
                out.append(_button(label, url, colours))
                button_done = True
            elif url:  # a standalone action link: ink, bold, no underline, ending in an arrow (DEC-101)
                out.append(
                    f'<p class="em-text" style="{p_style}"><a class="em-link" href="{html.escape(url, quote=True)}" '
                    f'style="color:{colours["link"]};font-weight:600;text-decoration:none;">{label}&nbsp;→</a></p>'
                )
            else:  # an address we won't link to: keep the words, drop the link
                out.append(f'<p class="em-text" style="{p_style}">{label}</p>')
            continue
        if para.startswith("## "):
            out.append(
                f'<h2 class="em-text" style="margin:8px 0 12px;font-family:{HEAD_FONT};font-size:19px;'
                f'line-height:26px;font-weight:600;letter-spacing:-0.01em;color:{colours["text"]};">'
                f"{_inline(para[3:], values, base, colours)}</h2>"
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
                f'line-height:26px;color:{colours["text"]};">{items}</ul>'
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
    """The One's number on a dark panel in both themes (DEC-101): the tier as a filled dash in its colour, never as
    text (DEC-098); the tier label in small capitals; the number in solid white."""
    shown = _one_number(data)
    if shown is None:
        return ""
    number, tier = shown
    tier_rows = ""
    if isinstance(tier, int) and tier in TIERS:
        name, colour = TIERS[tier]
        tier_rows = (
            '<tr><td style="padding:0 0 12px;"><table role="presentation" cellpadding="0" cellspacing="0" '
            f'border="0"><tr><td bgcolor="{colour}" width="24" height="4" style="width:24px;height:4px;'
            f'background:{colour};border-radius:2px;font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>'
            f'<tr><td style="font-family:{FONT};font-size:11px;line-height:16px;font-weight:600;'
            f'letter-spacing:0.12em;text-transform:uppercase;color:{PANEL_MUTED};">'
            f"Tier {tier} · {html.escape(name)}</td></tr>"
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:0 0 24px;"><tr><td bgcolor="{INK}" style="background:{INK};border-radius:16px;'
        'padding:24px;"><table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f"{tier_rows}"
        f'<tr><td style="padding:6px 0 0;font-family:{HEAD_FONT};font-size:64px;line-height:68px;font-weight:600;'
        f'letter-spacing:-0.02em;font-variant-numeric:tabular-nums;color:{WHITE};">No. {html.escape(str(number))}'
        f'</td></tr><tr><td style="padding:4px 0 0;font-family:{FONT};font-size:14px;line-height:20px;'
        f'color:{PANEL_MUTED};">Your number</td></tr></table></td></tr></table>'
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


_D = PALETTES["dark"]
_DARK_CSS = (
    "@media (prefers-color-scheme: dark) {"
    f" .em-page {{ background:{_D['page']} !important; }}"
    f" .em-card {{ background:{_D['card']} !important; border-color:{_D['border']} !important; }}"
    f" .em-text {{ color:{_D['text']} !important; }}"
    f" .em-muted {{ color:{_D['muted']} !important; }}"
    f" .em-panel {{ background:{_D['panel']} !important; }}"
    f" .em-line {{ border-color:{_D['line']} !important; }}"
    f" .em-link {{ color:{_D['link']} !important; }}"
    f" .em-btn-cell {{ background:{_D['button']} !important; }}"
    f" .em-btn {{ color:{_D['button_text']} !important; }}"
    f" .em-foot {{ background:{_D['foot']} !important; border-color:{_D['foot_line']} !important; }}"
    " .em-mark-light { display:none !important; }"
    " .em-mark-dark { display:block !important; }"
    " }"
    f" [data-ogsb] .em-page {{ background-color:{_D['page']} !important; }}"
    f" [data-ogsb] .em-card {{ background-color:{_D['card']} !important; }}"
    f" [data-ogsb] .em-panel {{ background-color:{_D['panel']} !important; }}"
    f" [data-ogsb] .em-btn-cell {{ background-color:{_D['button']} !important; }}"
    f" [data-ogsb] .em-foot {{ background-color:{_D['foot']} !important; }}"
    f" [data-ogsc] .em-text {{ color:{_D['text']} !important; }}"
    f" [data-ogsc] .em-muted {{ color:{_D['muted']} !important; }}"
    f" [data-ogsc] .em-link {{ color:{_D['link']} !important; }}"
    f" [data-ogsc] .em-btn {{ color:{_D['button_text']} !important; }}"
)


def _marks(base: str, theme: Theme) -> str:
    """The Spark mark: ink zeros on paper, white zeros in dark mode. In "auto" both are sent and the style block
    shows one; the dark one sits in a non-Outlook comment, since Outlook desktop has no dark mode and may ignore
    `display:none` on an image."""
    root = base.rstrip("/")

    def img(file: str, cls: str, extra: str = "") -> str:
        src = html.escape(f"{root}/{file}", quote=True)
        return (
            f'<img class="{cls}" src="{src}" width="22" height="26" alt="" '
            f'style="display:block;border:0;{extra}">'
        )

    if theme == "dark":
        return img(MARK_FILE_DARK, "em-mark-dark")
    if theme == "light":
        return img(MARK_FILE, "em-mark-light")
    return (
        img(MARK_FILE, "em-mark-light")
        + "<!--[if !mso]><!-->"
        + img(MARK_FILE_DARK, "em-mark-dark", "display:none;")
        + "<!--<![endif]-->"
    )


def shell(subject: str, inner: list[str], base: str, theme: Theme = "auto") -> str:
    """The page around a message (DEC-101): the ink header on paper, the white card with the subject as its
    headline, and the footer band."""
    colours = PALETTES["dark" if theme == "dark" else "light"]
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
        # Header: ink on paper, no band (DEC-101).
        '<tr><td style="padding:4px 4px 18px;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="padding-right:10px;">{_marks(base, theme)}</td>'
        f'<td class="em-text" style="font-family:{HEAD_FONT};font-size:19px;line-height:26px;font-weight:600;'
        f'letter-spacing:-0.03em;color:{colours["text"]};">1% Club</td></tr></table></td></tr>'
        f'<tr><td class="em-card" style="background:{colours["card"]};border:1px solid {colours["border"]};'
        'border-radius:16px;padding:32px 32px 16px;">'
        f'<h1 class="em-text" style="margin:0 0 20px;font-family:{HEAD_FONT};font-size:28px;line-height:34px;'
        f'font-weight:600;letter-spacing:-0.02em;color:{colours["text"]};">{html.escape(subject)}</h1>'
        + "".join(inner)
        + "</td></tr>"
        # Footer band.
        '<tr><td style="padding:16px 0 0;"><table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" border="0"><tr><td class="em-foot" bgcolor="{colours["foot"]}" '
        f'style="background:{colours["foot"]};border-top:1px solid {colours["foot_line"]};'
        'border-radius:0 0 12px 12px;padding:16px 24px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td class="em-muted" style="font-family:{FONT};font-size:13px;line-height:18px;color:{colours["muted"]};">'
        f'<span class="em-text" style="font-weight:500;color:{colours["text"]};">1% Club</span>'
        f" &nbsp;·&nbsp; {TAGLINE}</td>"
        f'<td class="em-muted" align="right" style="font-family:{FONT};font-size:13px;line-height:18px;'
        f'color:{colours["muted"]};">{ENDORSEMENT}</td></tr></table></td></tr></table></td></tr>'
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
            f'<h2 class="em-text" style="margin:12px 0 12px;font-family:{HEAD_FONT};font-size:19px;'
            f'line-height:26px;font-weight:600;letter-spacing:-0.01em;color:{colours["text"]};">'
            f"{html.escape(s)}</h2>"
        )
        inner.extend(message_body(tpl, data, base, theme))
        texts.append(f"{s}\n\n{text_part(tpl, data)}")
    return Email(subject, "\n\n".join(texts), shell(subject, inner, base, theme))
