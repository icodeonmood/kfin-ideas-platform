"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useState, useSyncExternalStore } from "react";

import { SparkMark } from "@/components/spark-mark";
import type { NavItem } from "@/lib/rbac";
import type { ShellData, ShellRow } from "@/server/shell";

import { AccountMenu, shortcutIsOn } from "./account-menu";
import { FOLD_COOKIE, foldValue } from "./fold";
import { IconFold, IconSearch, NavIcon } from "./icons";
import { useInboxUnread } from "./use-inbox-unread";

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

/** The dot's meaning in words, so it is never colour alone (F-A11Y.rules/4). A row's own words win: the section
 * knows what its dot means (an idea's stage; on the desk, amber is "Under a day left", not "Needs you"). */
const TONE_WORDS: Record<ShellRow["tone"], string> = {
  draft: "Draft",
  warn: "Needs you",
  bad: "Overdue",
  blue: "",
  neutral: "",
};

const dotWords = (r: ShellRow): string => r.words ?? TONE_WORDS[r.tone];

/** "Waiting on sharers" opens the desk on the tab its rows come from (C-SIDEBAR.anatomy/4, BLD-D013). */
const DESK_WAITING = "/desk?tab=waiting";

function SectionRows({ rows }: { rows: ShellRow[] }) {
  return (
    <>
      {rows.map((r) => (
        <Link key={r.href} href={r.href} className={r.meta ? "sb-r sb-dr" : "sb-r"} title={r.title}>
          <i className={`sb-d ${r.tone}`} aria-hidden="true" />
          {dotWords(r) ? <span className="vh">{dotWords(r)}: </span> : null}
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
  const inboxUnread = useInboxUnread(data.inboxUnread); // L-INBOX.rules/1, V-ACC.track/8

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
            <div className="sb-hr">
              <p className="sb-h">Waiting on sharers</p>
              {/* The desk opens on this tab; it has no way to focus its search box, so both go there (BLD-D013) */}
              <span className="sb-ha">
                <Link
                  href={DESK_WAITING}
                  className="sb-x"
                  aria-label="Search the desk"
                  title="Search the desk"
                >
                  <IconSearch />
                </Link>
                <Link
                  href={DESK_WAITING}
                  className="sb-va"
                  aria-current={pathname === "/desk" ? "page" : undefined}
                  aria-label="View all ideas waiting on sharers"
                >
                  View all
                </Link>
              </span>
            </div>
            <SectionRows rows={data.desk} />
          </section>
        ) : null}

        {data.committee?.length ? (
          <section className="sb-sec" aria-label="Closing soonest">
            <div className="sb-hr">
              <p className="sb-h">Closing soonest</p>
              <span className="sb-ha">
                <Link
                  href="/committee"
                  className="sb-va"
                  aria-current={pathname === "/committee" ? "page" : undefined}
                  aria-label="View all ideas closing soonest"
                >
                  View all
                </Link>
              </span>
            </div>
            <SectionRows rows={data.committee} />
          </section>
        ) : null}

        <AccountMenu data={data} items={account} placement="up" onShortcutChange={setShortcutOn} />
      </div>
    </nav>
  );
}
