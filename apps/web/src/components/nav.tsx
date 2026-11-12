"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { NavItem } from "@/lib/rbac";

const isCurrent = (pathname: string, href: string) => pathname === href || pathname.startsWith(href + "/");

/**
 * Main navigation (AT-B2-06) in the OFFER header (DEC-101). Links, in order, by keyboard; the current page is
 * announced with aria-current and shown by weight and a blue underline. Menus longer than the employee set
 * (data-long) take their own row in the header sooner.
 */
export function MainNav({ items }: { items: NavItem[] }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="hdr-nav main-nav" data-long={items.length > 4 ? "" : undefined}>
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
