---
id: C-PROMPT
title: Prompt box: type, speak, attach
rev: 1
status: baseline
source: reference/css/boards/Home.css
depends_on: [C-FILE, C-FIELD-MSG, F-MOTION]
last_delta: none
---

# C-PROMPT: Prompt box: type, speak, attach

The box where a problem is told. It is the brightest thing on Home and the heart of Tell it.

## `C-PROMPT.anatomy` Anatomy

A frosted glass box (radius 28px on Home, 720px wide; full width in the Tell it conversation; pinned to the bottom on phone):

1. A multi-line input that grows with its content. Placeholder on Home: "Describe what's getting in your way"; on Tell it, first message: "Describe the problem"; later: "Add a detail, like how often it happens or what you tried".
2. A tool row inside the box: attach (opens `C-FILE.uploader`), the microphone ("Speak instead"), and at the right end the round send button (ink when there is text, disabled before).
3. Under the box: one help line, "Say it in whichever language feels most natural to you." Then on Home and the empty Tell it, three starters as full-width soft rows: "A step customers keep calling about", "Something we redo by hand every month", "A screen that asks for the same thing twice". A starter fills the box with a sentence opener; it does not send.
4. While typing on Home, a live line under the box shows the first sorting guess (for example "Investor service") after "Sorting…".

## `C-PROMPT.keys` Keys

1. Enter sends (starts or adds to the draft). Shift+Enter adds a line. The box says so once there is text: "Enter starts your draft. Shift and Enter for a new line."
2. Ctrl/⌘+Enter moves to Check it when the draft is ready.
3. `P` from anywhere focuses the box (opens `S-04` first if not there).

## `C-PROMPT.voice` Speaking

| State | What shows |
|---|---|
| Idle | Mic button. On the empty phone screen with S3 "Voice first": a large mic with "Tap to start speaking" and "Not recording until you do" |
| Listening | The mic pulses; words appear in the box as they are recognised; "Listening. Up to 3 minutes." A stop control replaces send |
| Stopped | The transcript stays in the box, editable; the draft updates as if typed |
| Blocked (desktop) | Warning under the box: "Your browser has blocked the microphone. Allow it from the lock icon in the address bar, then try again. Or just type in the box above." |
| Blocked (phone) | "The microphone is off for this app. Turn it on in your phone's settings, or type above. Your words save as you go." |

Recording never starts on its own except under S3 "Voice first". Recognition and languages: `L-DRAFT.voice`.

## `C-PROMPT.attach` Attachments

Files and links attached here show as rows under the input, inside the box (`C-FILE.row`). They travel with the draft and appear again on Check it under Proof.

## `C-PROMPT.states` Other states

| State | What shows |
|---|---|
| Under 30 characters | Send is enabled, but the draft panel says "Your draft needs a little more first." and "Move to Review" stays disabled. Phone shows a live count: "30 more characters", then "Enough to work with" |
| Offline | The box works; the task bar says "Unsaved, you're offline"; a note says it will save when back online |
| Sending from Home | The words travel to `S-04B` as the first message (`P-ROUTES.state`) |

## `C-PROMPT.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Home.css` (classes: `.prompt`, `.cbox`)
- Resolved values as painted: `reference/computed/components.md`, section `C-PROMPT` (box, starter chip)
- Used on: `S-03`, `S-04`, `S-04B`
