---
id: S-H3
title: Share another way
rev: 1
status: baseline
source: reference/prototype/Ways.dc.html
depends_on: [C-SIDEBAR, C-CARD, C-PILL, L-DRAFT, L-NOTIFY]
last_delta: none
---

# S-H3: Share another way

**Route (proposed):** `/share/other-ways`. **Boards:** `Ways`

## `S-H3.purpose` Purpose

The other routes into 1% Club, and anything that has arrived by them and is waiting to be checked.

## `S-H3.layout` Layout

1. Title "Share another way"; "Each one lands here as a draft. Nothing is sent until you check it."
2. Three cards:
   - **Forward it from Outlook**: "Forward the thread that shows the problem. Your note on top becomes the draft." The address `[1% Club address]` with "Copy" and "Open in Outlook" (a mailto link).
   - **Message it in Teams**: "Chat with 1% Club in Teams. Paste screenshots straight in." "First time? Add it once:" three steps ("In Teams, open Apps from the side bar." "Search for 1% Club under Built for your org, and select Add." "Right-click it in the side bar and select Pin, so it stays there."). "Open in Teams" (a deep link).
   - **Use the 1% Club app**: a "Coming soon" pill; "Share from your phone, typed or spoken, in any language."; "Android and iOS"; "Tell me when it's out".
3. **Arrived from elsewhere** with a count ("2 to check"): rows with what arrived ("Fwd: SIP registration stuck again", "Voice message, 1 minute 12 seconds, in Telugu"), where from and when plus what was done ("From your email, today 9:14 am. One customer detail hidden." / "From Teams, yesterday 7:02 pm. Typed up in English."), and "Check and send" → `S-04B` on that draft.

## `S-H3.rules` Rules

1. "Copy" copies the address and the button reads "Copied" for two seconds (announced politely). No toast.
2. "Tell me when it's out" becomes "We'll tell you" once pressed (`L-NOTIFY/7`).
3. With nothing arrived, the section reads "Nothing waiting. Anything you forward or message shows up here." `NOT DRAWN:` wording.
4. Intake rules: `L-DRAFT.channels`.

## `S-H3.reference` Reference (generated)

### Board `Ways` (1440×1000)

- Canvas caption: H3 · Share another way: email, Teams, the app (coming soon), and what arrived
- Prototype: `reference/prototype/Ways.dc.html`
- Exact copy and controls in every state: `reference/copy/Ways.md`
- Board-specific CSS: `reference/css/boards/Ways.css`
- Default screenshot: `reference/shots/Ways.jpg`

Links out, as wired on the board: S-04 (Check and send)
