"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useState, useSyncExternalStore } from "react";

import { SparkMark } from "@/components/spark-mark";
import { COUNTS_EVENT } from "@/lib/inbox-events";
import type { NavItem } from "@/lib/rbac";
import type { ShellData, ShellRow } from "@/server/shell";

import { AccountMenu, shortcutIsOn } from "./account-menu";
import { FOLD_COOKIE, foldValue } from "./fold";
import { IconFold, IconSearch, NavIcon } from "./icons";

/** The current page, for aria-current: Home only on its own path; every other item on its path and below it. */
export function isCurrent(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

const tablet = {
  subscribe(cb: () => void) {
    const m = window.matchMedia("(max-width: 1100px)");
    m.addEventListener("change", cb);
    return () => m.removeEventListener("change", cb);
  },
  get: () => window.matchMedia("(max-width: 1100px)").matches,
  server: () => false,
};

/** Typing in any field, or a pop-up open, means P is a letter, not a shortcut. */
function typingSomewhere(target: EventTarget | null): boolean {
  const el = target instanceof HTMLElement ? target : null;
  if (!el) return false;
  if (el.isContentEditable) return true;
  if (el.closest("input, textarea, select, [contenteditable='true'], [role='textbox']")) return true;
  return Boolean(document.querySelector("dialog[open]"));
}

/** The dot's meaning in words, so it is never colour alone (F-A11Y.rules/4). */
const TONE_WORDS: Record<ShellRow["tone"], string> = {
  draft: "Draft",
  warn: "Needs you",
  bad: "Overdue",
  blue: "",
  neutral: "",
};

function SectionRows({ rows }: { rows: ShellRow[] }) {
  return (
    <>
      {rows.map((r) => (
        <Link key={r.href} href={r.href} className={r.meta ? "sb-r sb-dr" : "sb-r"} title={r.title}>
          <i className={`sb-d ${r.tone}`} aria-hidden="true" />
          {TONE_WORDS[r.tone] ? <span className="vh">{TONE_WORDS[r.tone]}: </span> : null}
          {r.meta ? (
            <span className="sb-dc">
              <span className="sb-dt">{r.title}</span>
              <span className="sb-dm">{r.meta}</span>
            </span>
          ) : (
            <span className="sb-dt">{r.title}</span>
          )}
        </Link>
      ))}
    </>
  );
}

/**
 * C-SIDEBAR: the same bar on every signed-in desktop screen. Brand and fold, "Share a problem" with its P hint, the
 * items for the person's roles, their drafts and ideas, and the account row with its menu (S-H6.rules/3). Folding
 * narrows it to icons, remembered per person and device; between 641 and 1100 px it starts folded (F-SPACE.breakpoints).
 * The bar never animates between screens (C-SIDEBAR.rules/3).
 */
export function Sidebar({
  personId,
  nav,
  data,
  folded: foldedAtLoad,
}: {
  personId: string;
  nav: NavItem[];
  data: ShellData;
  /** The person's own choice from the fold cookie; null means they have not chosen (the width decides). */
  folded: boolean | null;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [choice, setChoice] = useState<boolean | null>(foldedAtLoad);
  const isTablet = useSyncExternalStore(tablet.subscribe, tablet.get, tablet.server);
  const folded = choice ?? isTablet;
  const [shortcutOn, setShortcutOn] = useState(true);
  const barId = useId();
  // The Inbox's unread number (L-INBOX.rules/1): the server's `inboxCounts` when the page loads, then every count
  // the Inbox sends (`inbox:counts`, V-ACC.track/8) until the server's number changes again.
  const [served, setServed] = useState(data.inboxUnread);
  const [live, setLive] = useState<number | null>(null);
  if (served !== data.inboxUnread) {
    setServed(data.inboxUnread);
    setLive(null);
  }
  const inboxUnread = live ?? data.inboxUnread;

  const share = nav.find((n) => n.place === "new");
  const home = nav.find((n) => n.key === "home");
  const main = nav.filter((n) => n.place === "main" || n.place === "folded");
  const account = nav.filter((n) => n.place === "account");
  const ideasHref = nav.find((n) => n.key === "my-ideas")?.href ?? "/my-ideas";

  // The shell reads the fold state from <html data-fold>, so the content area widens with the bar.
  useEffect(() => {
    document.documentElement.dataset.fold = choice === null ? "auto" : choice ? "folded" : "open";
  }, [choice]);

  useEffect(() => {
    const t = window.setTimeout(() => setShortcutOn(shortcutIsOn()), 0);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    const onCounts = (e: Event) => {
      const unread = (e as CustomEvent<{ unread?: unknown } | null>).detail?.unread;
      if (typeof unread === "number") setLive(unread);
    };
    window.addEventListener(COUNTS_EVENT, onCounts);
    return () => window.removeEventListener(COUNTS_EVENT, onCounts);
  }, []);

  const toggleFold = () => {
    const next = !folded;
    setChoice(next);
    document.cookie = `${FOLD_COOKIE}=${foldValue(personId, next)}; path=/; max-age=31536000; samesite=lax`;
  };

  // P opens "Share a problem" from anywhere signed in, unless the person is typing or turned it off.
  useEffect(() => {
    if (!share) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "p" && e.key !== "P") return;
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
      if (!shortcutIsOn() || typingSomewhere(e.target)) return;
      e.preventDefault();
      router.push(share.href);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [router, share]);

  return (
    <nav id={barId} className="sbar" aria-label="Main" data-folded={folded ? "" : undefined}>
      <div className="sb-in">
        <div className="sb-top">
          <Link href={home?.href ?? "/"} className="sb-brand" aria-label="1% Club, Home">
            <SparkMark height={26} />
            <span className="sb-word" aria-hidden="true">
              1% Club
            </span>
          </Link>
          <button
            type="button"
            className="sb-fold"
            aria-controls={barId}
            aria-expanded={!folded}
            aria-label={folded ? "Open the side bar" : "Fold the side bar"}
            onClick={toggleFold}
          >
            <IconFold className="sb-fold-ic" />
          </button>
        </div>

        {share ? (
          <Link
            href={share.href}
            className="sb-new"
            data-tip={share.label}
            aria-keyshortcuts={shortcutOn ? "P" : undefined}
            aria-current={isCurrent(pathname, share.href) ? "page" : undefined}
          >
            <NavIcon navKey="share" className="sb-svg" />
            <span className="sb-l">{share.label}</span>
            {shortcutOn ? (
              <span className="sb-k" aria-hidden="true">
                P
              </span>
            ) : null}
          </Link>
        ) : null}

        <ul className="sb-nav" role="list">
          {main.map((item) => {
            const unread = item.key === "inbox" ? inboxUnread : 0;
            return (
              <li key={item.href} className={item.place === "folded" ? "sb-fonly" : undefined}>
                <Link
                  href={item.href}
                  className="sb-i"
                  data-tip={item.label}
                  aria-current={isCurrent(pathname, item.href) ? "page" : undefined}
                >
                  <NavIcon navKey={item.key} className="sb-svg" />
                  <span className="sb-l">{item.label}</span>
                  {unread ? (
                    <>
                      <span className="sb-n num" aria-hidden="true">
                        {unread}
                      </span>
                      <span className="vh">, {unread} unread</span>
                    </>
                  ) : null}
                </Link>
              </li>
            );
          })}
        </ul>

        {data.drafts.length ? (
          <section className="sb-sec" aria-label="Drafts">
            <p className="sb-h">Drafts</p>
            <SectionRows rows={data.drafts} />
          </section>
        ) : null}

        {data.ideas.length ? (
          <section className="sb-sec" aria-label="Your ideas">
            <div className="sb-hr">
              <p className="sb-h">Your ideas</p>
              <span className="sb-ha">
                <Link
                  href={`${ideasHref}#find`}
                  className="sb-x"
                  aria-label="Search your ideas"
                  title="Search your ideas"
                >
                  <IconSearch />
                </Link>
                <Link
                  href={ideasHref}
                  className="sb-va"
                  aria-current={pathname === ideasHref ? "page" : undefined}
                  aria-label="View all your ideas"
                >
                  View all
                </Link>
              </span>
            </div>
            <SectionRows rows={data.ideas} />
          </section>
        ) : null}

        {data.desk?.length ? (
          <section className="sb-sec" aria-label="Waiting on sharers">
            <p className="sb-h">Waiting on sharers</p>
            <SectionRows rows={data.desk} />
          </section>
        ) : null}

        {data.committee?.length ? (
          <section className="sb-sec" aria-label="Closing soonest">
            <p className="sb-h">Closing soonest</p>
            <SectionRows rows={data.committee} />
          </section>
        ) : null}

        <AccountMenu data={data} items={account} placement="up" onShortcutChange={setShortcutOn} />
      </div>
    </nav>
  );
}
