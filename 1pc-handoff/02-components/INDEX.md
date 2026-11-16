# Components

Shared components. Build the first group (C-BUTTON to C-FILE, plus the shell: C-SIDEBAR, C-PHONE-TABS, C-TASKBAR) before any screen.

| ID | Title | File | Depends on |
|---|---|---|---|
| `C-AVATAR` | Avatars and crew faces | `C-AVATAR.md` | F-COLOR, F-ICONS |
| `C-BUTTON` | Buttons | `C-BUTTON.md` | F-COLOR, F-TYPE, F-MOTION, F-SPACE |
| `C-CARD` | Cards, glass panels, notes and wells | `C-CARD.md` | F-COLOR, F-SPACE |
| `C-CHIP` | Chips (single and multi choice) | `C-CHIP.md` | F-COLOR, F-MOTION |
| `C-CREW-DECK` | Find your crew: deck of cards | `C-CREW-DECK.md` | C-PILL, C-AVATAR, C-SHEET-TEAMUP, F-MOTION |
| `C-DRAFT-LOADER` | Draft loader (six services, one bar) | `C-DRAFT-LOADER.md` | C-SKELETON, F-MOTION |
| `C-DRAFT-PANEL` | The draft, as a live document | `C-DRAFT-PANEL.md` | C-DRAFT-LOADER, C-HIDDEN, C-CHIP, C-SKELETON |
| `C-DROPDOWN` | Dropdown with multi-select | `C-DROPDOWN.md` | C-FIELD |
| `C-EMPTY` | Empty states | `C-EMPTY.md` | F-COPY, C-CARD, C-BUTTON |
| `C-FIELD-MSG` | Field errors and warnings | `C-FIELD-MSG.md` | F-COLOR, F-MOTION |
| `C-FIELD` | Text fields, text areas and labels | `C-FIELD.md` | F-COLOR, F-TYPE, C-FIELD-MSG |
| `C-FILE` | File and link rows, and the uploader | `C-FILE.md` | C-FIELD-MSG, C-SKELETON |
| `C-HIDDEN` | Hidden personal details | `C-HIDDEN.md` | C-CHIP, C-BUTTON |
| `C-INBOX-READER` | Inbox: list and reader | `C-INBOX-READER.md` | C-TABS, C-AVATAR, C-QCARD |
| `C-LISTEN` | Listen to the whole idea (player) | `C-LISTEN.md` | F-MOTION |
| `C-ONES-FAN` | The Ones: fan of cards | `C-ONES-FAN.md` | C-AVATAR, F-COLOR, F-MOTION |
| `C-PHONE-TABS` | Phone tab bar and top bars | `C-PHONE-TABS.md` | F-ICONS, F-SPACE |
| `C-PILL` | Status pill | `C-PILL.md` | F-COLOR |
| `C-PREVIEW` | Preview pop-up for an idea | `C-PREVIEW.md` | C-PILL, C-AVATAR, C-BUTTON, F-MOTION |
| `C-PROMPT` | Prompt box: type, speak, attach | `C-PROMPT.md` | C-FILE, C-FIELD-MSG, F-MOTION |
| `C-QCARD` | Questions card | `C-QCARD.md` | C-PILL, C-BUTTON |
| `C-SEARCH` | Search bar with filters inside | `C-SEARCH.md` | C-CHIP, C-FIELD |
| `C-SHEET-MERGE` | Merge sheet (review desk) | `C-SHEET-MERGE.md` | C-FIELD, C-BUTTON, C-FIELD-MSG |
| `C-SHEET-TEAMUP` | Team up request sheet | `C-SHEET-TEAMUP.md` | C-FIELD, C-DROPDOWN, C-BUTTON, C-PREVIEW |
| `C-SIDEBAR` | Sidebar (desktop navigation) | `C-SIDEBAR.md` | F-COLOR, F-ICONS, C-AVATAR |
| `C-SIMGRID` | Similar ideas: tiles and grid | `C-SIMGRID.md` | C-PILL, C-AVATAR, C-PREVIEW, C-SHEET-TEAMUP |
| `C-SKELETON` | Loading skeletons and spinner | `C-SKELETON.md` | F-COLOR, F-MOTION |
| `C-SORTS` | Sort control | `C-SORTS.md` | C-BUTTON, F-MOTION |
| `C-TABS` | Tabs with counts | `C-TABS.md` | F-MOTION |
| `C-TASKBAR` | Task bar: steps, save status, Save and close | `C-TASKBAR.md` | F-COLOR, F-MOTION |
| `C-TRACK` | Stage track | `C-TRACK.md` | F-MOTION, F-COLOR |
| `C-WORTH` | What it's worth: view and edit | `C-WORTH.md` | C-FIELD, C-CHIP |
