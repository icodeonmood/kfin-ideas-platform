---
id: C-PHONE-TABS
title: Phone tab bar and top bars
rev: 1
status: baseline
source: reference/css/phone-polish.css
depends_on: [F-ICONS, F-SPACE]
last_delta: none
---

# C-PHONE-TABS: Phone tab bar and top bars

## `C-PHONE-TABS.bar` Tab bar (root screens)

1. Five equal columns: Home, My ideas, Share, Wall, Inbox. Translucent white (94%) with blur, 1px top border, bottom padding `max(24px, safe-area + 4px)`.
2. A tab: 24px icon over an 11.5px label, min-height 52px, `#5F5F64`. Current: ink, label weight 600, icon stroke 2.2, and a 4px `--blue` dot under the label.
3. Share (centre): the icon sits in a 46×32px ink tile with 12px radius; label "Share". It opens `S-04`.
4. Inbox carries the unread count as a badge at the icon's top right, with a 2px white ring.
5. `nav` landmark; the current tab has `aria-current="page"`.

## `C-PHONE-TABS.top` Top row (root screens)

Brand at the left (18px word), the account button at the right (36px avatar with the tier ring, label "Your account, <name>, Tier 2, Glow"). Then one large title (`d1`, 32px).

## `C-PHONE-TABS.nav` Compact bar (child screens)

Three columns: Back (chevron + up to a few words, 16px 500, min 44px), a centred title (600 15px, max 180px, ellipsis), icon actions at the right (44px each). Background paper. One bar only.

## `C-PHONE-TABS.dock` Dock (task screens)

Replaces the tab bar on `S-04`, `S-04B`, `S-05`, `S-06B`, `S-R3`: paper fill, 1px top border, the forward button full width (56px), with any secondary action as a text button above or beside it.

## `C-PHONE-TABS.reference` Reference (generated)

- Source rules in the prototype: `reference/css/phone-polish.css` (classes: `.tabs`, `.tab`, `.pnav`, `.ptop`)
- Resolved values as painted: `reference/computed/components.md`, section `C-PHONE-TABS` (bar, tab, tab current, share)
- Used on: `S-01`, `S-03`, `S-06`, `S-07`, `S-08`, `S-WALL`, `S-09`, `S-H2`, `S-H5`, `S-R3`
