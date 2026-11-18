/**
 * S-06B.rules/2: "Open the conversation" after the review desk opened the idea mid-edit carries the person's unsaved
 * words into S-08's message box. The edit page writes them to this tab's sessionStorage under
 * `1pc.conversation.prefill.<IDEA-ref>`; the conversation reads them once, puts them in the box without sending, and
 * removes the key (BLD-C165). The words are the person's own, in their own browser: never in a URL, never logged,
 * and storage that cannot be used just gives nothing.
 */

export const prefillKey = (ref: string) => `1pc.conversation.prefill.${ref}`;

/** Keep the words for the conversation of `ref`. False when storage cannot be used (the box then starts empty). */
export function putPrefill(ref: string, text: string): boolean {
  try {
    if (!text.trim()) return false;
    window.sessionStorage.setItem(prefillKey(ref), text);
    return true;
  } catch {
    return false;
  }
}

/** The words kept for any of these references (the route's and the idea's own), once: each key is removed as read. */
export function takePrefill(refs: readonly string[]): string {
  try {
    const store = window.sessionStorage;
    let found = "";
    for (const ref of new Set(refs.filter(Boolean))) {
      const key = prefillKey(ref);
      const words = store.getItem(key);
      if (words === null) continue;
      store.removeItem(key);
      if (!found && words.trim()) found = words;
    }
    return found;
  } catch {
    return "";
  }
}
