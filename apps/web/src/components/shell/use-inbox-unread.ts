import { useEffect, useState } from "react";

import { COUNTS_EVENT } from "@/lib/inbox-events";

/**
 * The shell's Inbox number (L-INBOX.rules/1, V-ACC.track/8): the server's `inboxCounts(me).unread` when the page
 * loads, then every count the Inbox sends on `inbox:counts`, until the server's number changes again. C-SIDEBAR and
 * C-PHONE-TABS both read it, so both follow the same counts. PhoneTabs remounts after a task screen and starts again
 * from the server's number, which the shell fetches again after every navigation.
 */
export function useInboxUnread(served: number): number {
  const [base, setBase] = useState(served);
  const [live, setLive] = useState<number | null>(null);
  if (base !== served) {
    setBase(served);
    setLive(null);
  }

  useEffect(() => {
    const onCounts = (e: Event) => {
      const unread = (e as CustomEvent<{ unread?: unknown } | null>).detail?.unread;
      if (typeof unread === "number" && Number.isInteger(unread) && unread >= 0) setLive(unread);
    };
    window.addEventListener(COUNTS_EVENT, onCounts);
    return () => window.removeEventListener(COUNTS_EVENT, onCounts);
  }, []);

  return live ?? served;
}
