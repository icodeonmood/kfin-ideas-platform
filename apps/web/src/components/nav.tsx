"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { NavItem } from "@/lib/rbac";

/**
 * Main navigation (AT-B2-06) inside the header dock (DEC-099). Links, in order, by keyboard; the current page is
 * announced with aria-current and shown by weight. The design system's script adds the thumb (a glass bead that
 * flows to the current link); it is decorative and aria-hidden.
 */
export function MainNav({ items }: { items: NavItem[] }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="hdr-nav main-nav" data-thumb="a" data-thumb-current="page">
      {items.map((item) => {
        const current = pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link key={item.href} href={item.href} aria-current={current ? "page" : undefined}>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
