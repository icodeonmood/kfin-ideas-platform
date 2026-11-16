---
id: F-A11Y
title: Accessibility
rev: 1
status: baseline
source: reference/css/kit.css
depends_on: [F-COLOR, F-MOTION, F-SPACE]
last_delta: none
---

# Accessibility

Target: WCAG 2.2 level AA on every screen, desktop and phone. SEBI's digital accessibility requirements apply to KFintech's investor-facing products; this is an internal tool, but it is built to the same bar.

## `F-A11Y.rules` Rules every screen meets

1. **Contrast.** Text 4.5:1; large text (24px+, or 19px+ at weight 500) 3:1; control outlines and field borders 3:1. Measured on the real surface, including glass over ambient light.
2. **Focus is always visible.** 2px `--blue` outline, 3px offset, on every focusable element. Sticky bars never cover it (`F-SPACE.scroll/1`).
3. **Targets.** 44×44px minimum (`F-SPACE.targets`).
4. **Nothing by colour alone.** Status is a dot plus words. A selected chip has a ring and a filled wash plus `aria-pressed` or `aria-checked`; where a tick is drawn it is part of the state. Errors have an icon and words.
5. **Labels.** Every input has a visible label or a visually hidden one. Icon-only buttons have an `aria-label` that says what they do ("Close the preview", "Fold the side bar", "Add this question").
6. **Errors.** Shown under the field with `role="alert"`, the field gets `aria-invalid="true"` and `aria-describedby` pointing at the message, and focus moves to the first field in error on a failed submit.
7. **Live changes.** Counts, save status, countdowns and results that change without a page load are in an `aria-live="polite"` region. Timers that tick use `role="timer"` with a label and do not announce every second.
8. **Keyboard.** Everything works without a pointer. Tab order follows reading order. Escape closes the top-most pop-up, sheet or menu. Enter activates; in multi-line boxes Enter sends or advances and Shift+Enter adds a line, and the box says so.
9. **Dialogs.** Pop-ups and sheets use `role="dialog"`, `aria-modal="true"` and `aria-labelledby`; focus moves in on open, is trapped while open, and returns to the opener on close. Clicking the backdrop closes them. Background content is inert.
10. **Groups.** Radio-style chip sets use `role="radiogroup"` with `role="radio"` children and arrow-key movement; multi-select sets use `aria-pressed` buttons; tabs use `role="tablist"` / `role="tab"` / `aria-selected`.
11. **Drag has a click alternative.** Card decks and fans can be moved by buttons and keys as well as wheel, drag or swipe.
12. **Motion.** `prefers-reduced-motion` is honoured everywhere (`F-MOTION.reduced`). Nothing flashes.
13. **Text.** The page works at 200% zoom and with text spacing overrides; no fixed-height text containers except where the module says a title is single-line.
14. **Language.** `lang="en-IN"` on the document. Text entered or spoken in another language keeps its own `lang` where it is shown back.
15. **Headings.** One `h1` per screen; headings nest without skipping levels. Landmarks: `nav` (sidebar, labelled "Main"), `main`, `aside` for side panels with a label.
16. **Images and marks.** Decorative SVGs are `aria-hidden`. The brand mark has the accessible name "1% Club". Avatars with initials expose the person's name.

## `F-A11Y.shortcuts` Keyboard shortcuts

| Key | Does | Notes |
|---|---|---|
| `P` | Opens "Share a problem" from any signed-in screen | Ignored while typing in any field. Can be turned off from the account menu. Shown as a hint on the sidebar button |
| `Enter` | In the Tell it box: starts or adds to the draft. In Answer: goes to the next question | Shift+Enter adds a new line |
| `Ctrl/⌘ + Enter` | In Tell it: move to Check it when the draft is ready | |
| `Escape` | Closes the top-most pop-up, sheet, menu or filter panel | |
| `←` `→` | Move between cards in the Ones fan and the crew deck when focus is inside | Also the Previous / Next buttons |
| `Backspace` | In the My ideas search with an empty box: removes the last filter chip | |

## `F-A11Y.audit` What to verify on the built screens

1. Automated: axe-core clean on every route in every state listed in its screen module.
2. Manual, per journey (`J-*`): keyboard-only pass; screen-reader pass (NVDA on Windows with Chrome or Edge, VoiceOver on iOS); 200% zoom; reduced motion on.
3. The prototype was audited for rendered text contrast: 13 text items remain below AA and are all disabled buttons or decorative text on gradient cards on the phone crew screen. Re-measure those in the build.
