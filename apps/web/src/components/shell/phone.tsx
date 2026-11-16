"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { SparkMark } from "@/components/spark-mark";
import type { NavItem } from "@/lib/rbac";
import type { ShellData } from "@/server/shell";

import { AccountMenu } from "./account-menu";
import { IconBack, NavIcon } from "./icons";
import { isCurrent } from "./sidebar";

/**
 * C-PHONE-TABS.bar: Home, My ideas, Share (the ink tile in the middle), Wall, Inbox, at 640 px and narrower. The
 * current tab is ink, heavier and dotted in blue; Inbox carries the unread count. Never animates between screens.
 */
export function PhoneTabs({ nav, unread }: { nav: NavItem[]; unread: number }) {
  const pathname = usePathname();
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
            aria-label={share ? t.label : count ? `${t.label}, ${count} new` : undefined}
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

/**
 * C-PHONE-TABS.dock: on a task screen (Tell it, Check it, Edit, Answer) the forward action sits in a bottom dock in
 * place of the tab bar, full width at 56 px, with any secondary action as a text button above it. On desktop the dock's
 * contents sit at the end of the flow, bottom right (F-SPACE.cta/1).
 */
export function Dock({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <div className="dock" role="group" aria-label={label}>
      {children}
    </div>
  );
}
