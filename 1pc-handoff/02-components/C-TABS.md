---
id: C-TABS
title: Tabs with counts
rev: 1
status: baseline
source: reference/css/boards/Desk.css
depends_on: [F-MOTION]
last_delta: none
---

# C-TABS: Tabs with counts

1. `C-TABS/1` A row of text tabs, each with an optional count after the label (tabular figures, `--mute`). Height 46px, 500 16px. The selected tab is ink with a 2px ink underline and its count in a small ink badge with white figures; others are `--mute2` with the count in grey. Tabs are 28px apart.
2. `C-TABS/2` `role="tablist"`, `role="tab"`, `aria-selected`; arrow keys move between tabs; the panel is `role="tabpanel"`.
3. `C-TABS/3` The underline slides from the old tab to the new one and stretches to fit (`F-MOTION.inside`, "Tabs slide").
4. `C-TABS/4` Changing tab keeps the page's scroll position at the top of the list and updates the URL.
5. `C-TABS/5` A tab with a zero count stays visible and selectable; its panel shows an empty state.
6. `C-TABS/6` On phone, tabs that do not fit scroll sideways; the selected one is scrolled into view.

Uses: `S-R1` (To review, Waiting on the sharer, Answered back to you, Decided this week), `S-R4` (In the window, Reversed, Expired), `S-H5` (All, Needs you, Unread, Archived), `S-07` (Yours, Teamed up).

## `C-TABS.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Desk.css` (classes: `.mtab`)
- Resolved values as painted: `reference/computed/components.md`, section `C-TABS` (tab, tab on)
- Used on: `S-07`, `S-R1`, `S-R4`
