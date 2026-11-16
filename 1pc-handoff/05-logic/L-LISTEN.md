---
id: L-LISTEN
title: Reading an idea aloud
rev: 1
status: baseline
source: reference/copy/DeskIdea.md
depends_on: [L-HIDE]
last_delta: none
---

# L-LISTEN: Reading an idea aloud

1. `L-LISTEN/1` Generates speech for an idea in six parts (The problem, How often, Who it affects, What it's worth, Attached, Fix) and returns one audio stream plus the start time of each part and the total length.
2. `L-LISTEN/2` The script is built from the idea as the reviewer sees it: masked, with answers folded into their parts. "Attached" is read as a description of each file ("One file: a branch call log for November. No screenshot of the SMS yet."). An empty part is read briefly ("No fix suggested. It was optional.").
3. `L-LISTEN/3` Audio is regenerated when the idea's content changes (an edit, an answer, a revision) and cached otherwise.
4. `L-LISTEN/4` Playback speeds 1×, 1.25×, 1.5×, 2× are done on the client.
5. `L-LISTEN/5` "Save for offline" lets the client keep the audio for that idea on the device; it is removed when the idea is decided or after 30 days.
6. `L-LISTEN/6` Voice: one clear Indian English voice. `OPEN:` voice choice and provider.
7. `L-LISTEN/7` If generation fails the player shows "Couldn't prepare the audio. Try again." and the rest of the page is unaffected (`NOT DRAWN:` default).

## `L-LISTEN.touchpoints` Where the front end depends on this

`S-R2`, `C-LISTEN`
