"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { SparkMark } from "@/components/spark-mark";
import type { NavItem } from "@/lib/rbac";
import type { ShellData } from "@/server/shell";

import { AccountMenu } from "./account-menu";
import { IconBack, NavIcon } from "./icons";
import { isCurrent } from "./sidebar";
import { useInboxUnread } from "./use-inbox-unread";

/**
 * C-PHONE-TABS.bar: Home, My ideas, Share (the ink tile in the middle), Wall, Inbox, at 640 px and narrower. The
 * current tab is ink, heavier and dotted in blue; Inbox carries the unread count, the server's and then each one the
 * Inbox sends, as the sidebar does (L-INBOX.rules/1). Never animates between screens.
 */
export function PhoneTabs({ nav, unread: served }: { nav: NavItem[]; unread: number }) {
  const pathname = usePathname();
  const unread = useInboxUnread(served);
  const tabs = nav.filter((n) => n.tab).sort((a, b) => (a.tab ?? 0) - (b.tab ?? 0));
  return (
    <nav className="ptabs" aria-label="Main">
      {tabs.map((t) => {
        const share = t.place === "new";
        const count = t.key === "inbox" ? unread : 0;
        const label = share ? "Share" : t.label;
        return (
          <Link
            key={t.href}
            href={t.href}
            className={share ? "ptab share" : "ptab"}
            aria-current={isCurrent(pathname, t.href) ? "page" : undefined}
          >
            {share ? (
              <span className="ptab-t">
                <NavIcon navKey={t.key} size={20} />
              </span>
            ) : (
              <NavIcon navKey={t.key} size={24} />
            )}
            {count ? (
              <span className="badge num" aria-hidden="true">
                {count}
              </span>
            ) : null}
            <span className="ptab-l">{label}</span>
            {share ? <span className="vh"> a problem</span> : null}
            {count ? <span className="vh">, {count} new</span> : null}
          </Link>
        );
      })}
    </nav>
  );
}

/** C-PHONE-TABS.top: the brand and the account button on the root screens (Home, My ideas, Wall, Inbox). The account
 * button opens the account menu (S-H6.rules/3). */
export function PhoneTop({
  homeHref,
  data,
  account,
}: {
  homeHref: string;
  data: ShellData;
  account: NavItem[];
}) {
  return (
    <div className="ptop">
      <Link href={homeHref} className="ptop-brand" aria-label="1% Club, Home">
        <SparkMark height={26} />
        <span aria-hidden="true">1% Club</span>
      </Link>
      <AccountMenu data={data} items={account} placement="down" />
    </div>
  );
}

/**
 * C-PHONE-TABS.nav: the one compact bar on a phone child screen. Back with a few words, a short centred title, icon
 * actions at the right. Shown at 640 px and narrower only; a screen renders it at the top of its content.
 */
export function PhoneBar({
  back,
  title,
  actions,
}: {
  back: { href: string; label: string };
  title: string;
  actions?: ReactNode;
}) {
  return (
    <div className="pnav">
      <Link href={back.href} className="pback">
        <IconBack />
        <span>{back.label}</span>
      </Link>
      <p className="pnav-t" aria-hidden="true">
        {title}
      </p>
      <div className="pnav-r">{actions}</div>
    </div>
  );
}

/** The width at which the dock is fixed to the foot of the screen (shell.css's phone rules). */
export const DOCK_PHONE = "(max-width: 640px)";

const onPhoneChange = (cb: () => void) => {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const m = window.matchMedia(DOCK_PHONE);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
};
const phoneNow = () => typeof window.matchMedia === "function" && window.matchMedia(DOCK_PHONE).matches;
const phoneOnServer = () => false;
/** The shell's slot for a phone's dock; null on a desk, on the server and without the shell. */
const dockSlot = () => (phoneNow() ? document.querySelector<HTMLElement>("main#main > .dock-root") : null);
const noSlotOnServer = () => null;

/** Every phone dock on screen with its height. The page keeps room for the tallest: `--dock-h` on <html>, with
 * `data-dock` while there is one (shell.css). */
const heights = new Map<symbol, number>();
function publishDockHeight() {
  const root = document.documentElement;
  if (!heights.size) {
    root.style.removeProperty("--dock-h");
    root.removeAttribute("data-dock");
    return;
  }
  root.style.setProperty("--dock-h", `${Math.ceil(Math.max(...heights.values()))}px`);
  root.setAttribute("data-dock", "");
}

/**
 * C-PHONE-TABS.dock: on a task screen (Tell it, Check it, Edit, Answer) the forward action sits in a bottom dock in
 * place of the tab bar, full width at 56 px, with any secondary action as a text button above it. On desktop the dock's
 * contents sit at the end of the flow, bottom right (F-SPACE.cta/1), where the page put it.
 *
 * On a phone (BLD-D028) the dock is fixed to the screen, so it renders through a portal into the shell's `.dock-root`
 * at the end of `main#main`: a panel's blur, a sheet's transform or an arriving block can never make itself the box
 * the dock is placed in, and the dock stays in the main landmark, last in the reading order as before. It measures its
 * own height for the page's room under it and for where the browser scrolls a focused field (`--dock-h`). Without the
 * shell (a test, a public page) it stays where it is. Its contents leave the page's own elements: style them by their
 * own class, never under a page class, and give a submit button `form=` if the dock is ever inside a form.
 */
export function Dock({
  children,
  label,
  className,
}: {
  children: ReactNode;
  label?: string;
  /** A page's own name for its dock (S-06B's `ed-dock`), added to `dock`. */
  className?: string;
}) {
  const phone = useSyncExternalStore(onPhoneChange, phoneNow, phoneOnServer);
  const slot = useSyncExternalStore(onPhoneChange, dockSlot, noSlotOnServer);
  const box = useRef<HTMLDivElement>(null);
  const away = slot !== null;
  // On a phone the dock measures itself, and again whenever it moves into or out of the slot (a new element)
  useEffect(() => {
    const el = box.current;
    if (!phone || !el) return;
    const key = Symbol("dock");
    const measure = () => {
      heights.set(key, el.getBoundingClientRect().height);
      publishDockHeight();
    };
    measure();
    const seen = typeof ResizeObserver === "function" ? new ResizeObserver(measure) : null;
    seen?.observe(el);
    return () => {
      seen?.disconnect();
      heights.delete(key);
      publishDockHeight();
    };
  }, [phone, away]);

  const dock = (
    <div ref={box} className={className ? `dock ${className}` : "dock"} role="group" aria-label={label}>
      {children}
    </div>
  );
  return slot ? createPortal(dock, slot) : dock;
}
