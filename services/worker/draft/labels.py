"""Where and when a draft was saved, as the screens say it (A-API.conventions/6: computed on the server, so every
screen agrees). Office time (IST). The wording is the boards' (`reference/copy/Compose.md`, `ComposeResume.md`,
`PhoneCompose.md`, `MyIdeas.md`):

- sidebar and lists: "Friday, on your phone", "Yesterday, on this laptop";
- resuming: "Last saved on your phone, Friday 8:42 pm.";
- the existing-draft prompt: "You have a draft from Friday" and "Last saved on your phone, 8:42 pm." (on the same
  device: "Saved on this phone, 8:42 pm.");
- the save status: "Saved at 1:38 pm";
- My ideas: "Saved yesterday, on this laptop", "Saved 8:42 pm Friday, on your phone";
- a message: "Just now", "Friday, 8:42 pm, on your phone".
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
WEEK_DAYS = 6  # within this many days a day is named by its weekday ("Friday"); older ones carry the date


def clock(at: dt.datetime) -> str:
    local = at.astimezone(IST)
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'am' if local.hour < 12 else 'pm'}"


def day(at: dt.datetime, now: dt.datetime) -> str:
    """ "today", "yesterday", "Friday", or "Friday 13 November" further back (lower case for today and yesterday,
    so a sentence can carry them; `capital` lifts the first letter)."""
    a, n = at.astimezone(IST).date(), now.astimezone(IST).date()
    gap = (n - a).days
    if gap <= 0:
        return "today"
    if gap == 1:
        return "yesterday"
    if gap <= WEEK_DAYS:
        return a.strftime("%A")
    return f"{a.strftime('%A')} {a.day} {a.strftime('%B')}"


def capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def where(device: str | None, this_device: bool) -> str:
    if device not in ("phone", "laptop"):
        return ""
    return f"on this {device}" if this_device else f"on your {device}"


def saved_labels(
    at: dt.datetime | None, device: str | None, this_device: bool, now: dt.datetime
) -> dict[str, str] | None:
    if at is None:
        return None
    d, t, w = day(at, now), clock(at), where(device, this_device)
    on = f", {w}" if w else ""
    when = t if d == "today" else f"{capital(d) if d == 'yesterday' else d} {t}"
    if d == "today":
        my_ideas = f"Saved {t}{on}"
    elif d == "yesterday":
        my_ideas = f"Saved yesterday{on}"
    else:
        my_ideas = f"Saved {t} {d}{on}"
    if this_device and w:
        line = f"Saved {w}, {t}."
    elif w:
        line = f"Last saved {w}, {t}."
    else:
        line = f"Last saved {t}."
    return {
        "sidebar": f"{capital(d)}{on}",
        "resume": f"Last saved {w}, {when}." if w else f"Last saved {when}.",
        "prompt_day": d,
        "prompt_line": line,
        "status": f"Saved at {t}",
        "my_ideas": my_ideas,
    }


def message_label(at: dt.datetime, device: str | None, this_device: bool, now: dt.datetime) -> str:
    if (now - at).total_seconds() < 60:
        return "Just now"
    d = day(at, now)
    w = where(device, this_device)
    stamp = clock(at) if d == "today" else f"{capital(d)}, {clock(at)}"
    return f"{stamp}, {w}" if w else stamp
