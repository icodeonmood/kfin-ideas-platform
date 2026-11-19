"""Where and when a draft was saved, as the screens say it (A-API.conventions/6: computed on the server, so every
screen agrees). Office time (IST). The wording is the boards' (`reference/copy/Compose.md`, `ComposeResume.md`,
`PhoneCompose.md`, `MyIdeas.md`):

- sidebar and lists: "Friday, on your phone", "Yesterday, on this laptop";
- resuming: "Last saved on your phone, Friday 8:42 pm.", always with its day ("today 3:12 pm", as the boards write
  "asked, today 11:20 am"; BLD-C158);
- the existing-draft prompt: "You have a draft from Friday" and "Last saved on your phone, 8:42 pm." (on the same
  device: "Saved on this phone, 8:42 pm.");
- the save status: "Saved at 1:38 pm"; saved on an earlier day, the day and time a picked-up message reads ("Saved
  Monday, 10:59 pm", "Saved yesterday, 10:59 pm"; BLD-C192);
- My ideas: "Saved yesterday, on this laptop", "Saved 8:42 pm Friday, on your phone";
- a message: "Just now", "Friday, 8:42 pm, on your phone"; an earlier one always with its day, time and device
  ("Today, 3:12 pm, on your laptop"; BLD-C185).
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
WEEK_DAYS = 6  # within this many days a day is named by its weekday ("Friday"); older ones carry the date
TYPED_UP_IN_ENGLISH = "Typed up in English"  # an English copy's label (L-DRAFT.voice/4, the `Ways` board)


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
    when = f"{d} {t}"  # S-04B's "Friday 8:42 pm": the day mid-sentence, lower case for today and yesterday
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
        "status": f"Saved at {t}" if d == "today" else f"Saved {stamp(at, now)}",  # BLD-C192
        "my_ideas": my_ideas,
    }


def stamp(at: dt.datetime, now: dt.datetime) -> str:
    """The day and time a picked-up message reads (BLD-C185), mid-sentence: "Monday, 10:59 pm", "yesterday, 10:59
    pm". The task bar's save status on an earlier day says it after "Saved" (BLD-C192)."""
    return f"{day(at, now)}, {clock(at)}"


def earlier_label(at: dt.datetime, device: str | None, this_device: bool, now: dt.datetime) -> str:
    """An earlier message, as S-04B draws one picked up from a saved draft: day, time and device, never "Just now"
    ("Friday, 8:42 pm, on your phone"; today reads "Today, 3:12 pm, on your laptop", as the side bar's "Today, on
    your laptop" and the conversation's "Today, 10:07 am"; BLD-C185)."""
    when = capital(stamp(at, now))
    w = where(device, this_device)
    return f"{when}, {w}" if w else when


def message_label(at: dt.datetime, device: str | None, this_device: bool, now: dt.datetime) -> str:
    if (now - at).total_seconds() < 60:
        return "Just now"
    return earlier_label(at, device, this_device, now)
