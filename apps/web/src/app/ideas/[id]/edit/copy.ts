/**
 * S-06B "Edit after sharing": the words on the screen, word for word from 1pc-handoff/reference/copy/Edit.md and
 * PhoneEdit.md. Lines the server words are shown as the API sends them: the bar ("Edit IDEA-…", "Shared …"), "Back to
 * your idea", the sorting note, the side panel's dates, the declaration, "Saved. The review desk will see the latest
 * version." and every refusal (`edit_window_closed`, V-FIELDS.checkit/15). The parts reuse S-05's words
 * (share/[id]/check/copy.ts). Nothing here is invented: a line the boards do not draw says NOT DRAWN and where it
 * comes from.
 */

export const EDIT_COPY = {
  heading: "Edit your problem",
  line: "Change anything that isn’t right. Nothing changes for anyone else until you save.",

  words: { heading: "Your problem", line: "The review desk reads this first" },
  sorting: { heading: "Is this sorted right?", line: "Sorting decides who reviews it" },
  proof: {
    heading: "Anything that shows it?",
    links: "Link to a report, dashboard or ticket",
    linkInput: "Or paste a link to a report, dashboard or ticket",
    addLink: "Add link",
  },
  fix: {
    heading: "Your fix",
    title: "Got an idea how to solve it?",
    line: "It helps the review desk weigh it. Skipping it is fine: problems on their own get picked too.",
  },
  optional: "Optional",
  side: "What happens when you save",

  back: "Back to your idea",
  cancel: "Cancel",
  save: "Save changes",
  /** C-TASKBAR.save's word while a save is on its way. */
  saving: "Saving…",
  /** L-SUBMIT.edit/2, when the server sends no words of its own. */
  saved: "Saved. The review desk will see the latest version.",
  /** S-06B.rules/2: the way on after `edit_window_closed`. */
  conversation: "Open the conversation",
  /**
   * NOT DRAWN (S-06B.layout/7: Cancel "discards after an in-place confirm if there are unsaved changes"; no words are
   * drawn). The confirm says only drawn lines: the task bar's "Unsaved changes" and the heading's "Nothing changes for
   * anyone else until you save.", and pressing Cancel again leaves (BLD-C163).
   */
  cancelConfirm: { lead: "Unsaved changes", line: "Nothing changes for anyone else until you save." },

  /** PhoneEdit.md: the phone's own lines. */
  phone: {
    linkInput: "Or paste a link",
    addLink: "Add",
    pick: {
      label: "Add a photo or file",
      line: "A screenshot of the SMS, a call log, or a report with the time or money it costs",
    },
    declaration:
      "Saving confirms there’s no customer personal data in it or its files, and it’s your own work or credited.",
    /** The side panel's second line on a phone (no "instead"); the phone draws two of the three. */
    sideClose: "Editing closes when the review desk opens it. After that, you can add a note for them.",
  },
} as const;
