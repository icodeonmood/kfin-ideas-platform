/**
 * The window event that carries every Inbox count when it changes (L-INBOX.rules/1, V-ACC.track/8): the Inbox
 * reader sends it after opening, marking, archiving or answering an item and on its 30 s refresh; the shell's
 * sidebar listens, so its unread number moves with the Inbox's. Its `detail` is `InboxCounts`.
 */
export const COUNTS_EVENT = "inbox:counts";
