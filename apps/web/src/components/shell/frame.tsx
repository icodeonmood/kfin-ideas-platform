"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { SparkMark } from "@/components/spark-mark";
import type { NavItem } from "@/lib/rbac";
import type { ShellData } from "@/server/shell";

import { PhoneTabs, PhoneTop } from "./phone";
import { Sidebar } from "./sidebar";

export type ShellMode = "display" | "public" | "task" | "app";

/** The wall displays run full screen with no chrome (S-OFFICE, S-LAUNCH). */
const DISPLAY = /^\/(launch|constellation|display)(\/|$)/;
/** Task screens (F-SPACE.shell/3): Tell it, a draft, Check it, Edit, Answer. They mount their own task bar and dock. */
const TASK = [/^\/share$/, /^\/share\/[0-9a-f-]{36}(\/check)?$/, /^\/ideas\/[^/]+\/(edit|answer)$/];
/** Root screens get the phone's brand row (C-PHONE-TABS.top); every other screen draws its own compact bar. */
const ROOT = [/^\/$/, /^\/home$/, /^\/my-ideas$/, /^\/wall$/, /^\/inbox$/];
/** Full ambient light (F-COLOR.glass/1); every other signed-in screen is quiet, keeping warm colour for "needs you". */
const FULL_LIGHT = [
  /^\/$/,
  /^\/home$/,
  /^\/share$/,
  /^\/share\/[0-9a-f-]{36}$/,
  /^\/crew$/,
  /^\/wall$/,
  /^\/one$/,
  /^\/profile$/,
  /^\/share\/other-ways$/,
  /^\/how-it-works$/,
];

export function shellMode(pathname: string, signedIn: boolean): ShellMode {
  if (DISPLAY.test(pathname)) return "display";
  if (!signedIn) return "public";
  return TASK.some((r) => r.test(pathname)) ? "task" : "app";
}

export function lightFor(pathname: string, mode: ShellMode): "full" | "quiet" {
  if (mode === "public") return "full";
  return FULL_LIGHT.some((r) => r.test(pathname)) ? "full" : "quiet";
}

export function Ambient({ light }: { light: "full" | "quiet" }) {
  return (
    <div className="amb" data-light={light} aria-hidden="true">
      <i className="a1" />
      <i className="a2" />
      <i className="a3" />
      <i className="a4" />
      <i className="a5" />
      <i className="a6" />
    </div>
  );
}

/**
 * The signed-in shell (F-SPACE.shell; C-SIDEBAR, C-PHONE-TABS) and the signed-out frame, chosen by the path so no page
 * has to move into a route group mid-build (BLD-D011). Display screens get no chrome. Signed-out screens get a simple
 * brand row. Signed-in screens get the sidebar on desktop, and on a phone the brand row on root screens and the tab bar
 * everywhere but task screens, which mount their own dock. Ambient light sits behind it all, full or quiet by screen.
 */
export function ShellFrame({
  signedIn,
  personId,
  nav,
  data,
  folded,
  banners,
  children,
}: {
  signedIn: boolean;
  personId: string | null;
  nav: NavItem[];
  data: ShellData | null;
  folded: boolean | null;
  banners?: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const mode = shellMode(pathname, signedIn && Boolean(data));
  const main = (
    <main id="main" tabIndex={-1}>
      {children}
    </main>
  );

  if (mode === "display") return main;

  if (mode === "public" || !data || !personId) {
    return (
      <div className="shell shell-public" data-mode="public">
        <Ambient light="full" />
        <header className="pub-top">
          <Link href="/" className="pub-brand" aria-label="1% Club, Home">
            <SparkMark height={26} />
            <span aria-hidden="true">1% Club</span>
          </Link>
        </header>
        {main}
      </div>
    );
  }

  const home = nav.find((n) => n.key === "home")?.href ?? "/";
  const account = nav.filter((n) => n.place === "account");
  // On a phone the tab bar is the same five for everyone, so the role items (Review desk, Ones Committee) join the
  // account menu there; the review side has no phone board but must still be reachable (P-ROUTES.screens).
  const phoneAccount = [...nav.filter((n) => n.place === "main" && !n.tab), ...account];
  return (
    <div className="shell" data-mode={mode}>
      <Ambient light={lightFor(pathname, mode)} />
      <Sidebar personId={personId} nav={nav} data={data} folded={folded} />
      {ROOT.some((r) => r.test(pathname)) ? (
        <PhoneTop homeHref={home} data={data} account={phoneAccount} />
      ) : null}
      {banners}
      {main}
      {mode === "app" ? <PhoneTabs nav={nav} unread={data.inboxUnread} /> : null}
    </div>
  );
}
