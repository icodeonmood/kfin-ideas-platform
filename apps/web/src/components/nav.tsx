"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import type { NavItem } from "@/lib/rbac";

type Thumb = { go: (el: Element | null, instant?: boolean) => void };

const isCurrent = (pathname: string, href: string) => pathname === href || pathname.startsWith(href + "/");

/**
 * Main navigation (AT-B2-06) inside the header dock (DEC-099). Links, in order, by keyboard; the current page is
 * announced with aria-current and shown by weight. The design system's script adds the thumb (a glass bead that
 * flows to the current link); it is decorative and aria-hidden.
 *
 * The route owns aria-current, not the script: the script moves aria-current to whichever link is clicked, so a
 * click that opens a new tab (Ctrl, Cmd, Shift, Alt or a middle click) is kept from reaching it, and after every
 * route change aria-current is set again from the path and the bead is sent to it (Back, the brand, home cards).
 * Menus longer than the employee set (data-long) take their own row in the dock sooner.
 */
export function MainNav({ items }: { items: NavItem[] }) {
  const pathname = usePathname();
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const nav = ref.current;
    if (!nav) return;
    const keepNewTabClicks = (e: MouseEvent) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) e.stopPropagation();
    };
    nav.addEventListener("click", keepNewTabClicks, true);
    return () => nav.removeEventListener("click", keepNewTabClicks, true);
  }, []);

  useEffect(() => {
    const nav = ref.current;
    if (!nav) return;
    let current: Element | null = null;
    nav.querySelectorAll<HTMLAnchorElement>(":scope > a[href]").forEach((a) => {
      if (isCurrent(pathname, a.getAttribute("href") ?? "")) {
        a.setAttribute("aria-current", "page");
        current = a;
      } else a.removeAttribute("aria-current");
    });
    (nav as HTMLElement & { __opcThumb?: Thumb }).__opcThumb?.go(current);
  }, [pathname]);

  return (
    <nav
      ref={ref}
      aria-label="Main"
      className="hdr-nav main-nav"
      data-thumb="a"
      data-thumb-current="page"
      data-long={items.length > 4 ? "" : undefined}
    >
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={isCurrent(pathname, item.href) ? "page" : undefined}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
