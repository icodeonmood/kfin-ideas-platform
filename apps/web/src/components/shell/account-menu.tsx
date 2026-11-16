"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import type { NavItem } from "@/lib/rbac";
import type { ShellData } from "@/server/shell";

import { IconKey, IconSignOut, NavIcon } from "./icons";

export const P_KEY = "1pc:shortcut-p";

/** The `P` shortcut (F-A11Y.shortcuts): on unless the person turned it off here. Remembered per device. */
export function shortcutIsOn(): boolean {
  try {
    return window.localStorage.getItem(P_KEY) !== "off";
  } catch {
    return true;
  }
}

/**
 * The account menu (S-H6.rules/3, NOT DRAWN default: a small menu by the account button). The account row in the
 * sidebar opens it upward; the phone's account button opens it downward. It holds the account links for the person's
 * roles (Profile once it lands, Admin, Delivery), the P shortcut switch and Sign out. A disclosure, not an ARIA menu:
 * Tab moves through it, Escape closes it and returns focus to the button, a click outside closes it.
 */
export function AccountMenu({
  data,
  items,
  placement,
  onShortcutChange,
}: {
  data: ShellData;
  items: NavItem[];
  placement: "up" | "down";
  onShortcutChange?: (on: boolean) => void;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [shortcutOn, setShortcutOn] = useState(true);
  const menuId = useId();
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setShortcutOn(shortcutIsOn()), 0);
    return () => window.clearTimeout(t);
  }, []);

  const close = useCallback((returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) button.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        close(true);
      }
    };
    const onPointer = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!panel.current?.contains(t) && !button.current?.contains(t)) close(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open, close]);

  // A new screen closes the menu.
  const [openedOn, setOpenedOn] = useState(pathname);
  if (openedOn !== pathname) {
    setOpenedOn(pathname);
    setOpen(false);
  }

  const toggleShortcut = () => {
    const next = !shortcutOn;
    setShortcutOn(next);
    onShortcutChange?.(next);
    try {
      window.localStorage.setItem(P_KEY, next ? "on" : "off");
    } catch {
      /* a private window: the choice lasts for this page */
    }
  };

  const tierLine = data.tier && data.tierName ? `Tier ${data.tier}, ${data.tierName}` : null;
  const label = ["Your account", data.name, tierLine].filter(Boolean).join(", ");

  return (
    <div className={`acct acct-${placement}`}>
      {open ? (
        <div id={menuId} ref={panel} className="acct-menu menu">
          <ul role="list">
            {items.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="acct-mi">
                  <NavIcon navKey={item.key} size={18} />
                  {item.label}
                </Link>
              </li>
            ))}
            <li>
              <button
                type="button"
                role="switch"
                aria-checked={shortcutOn}
                className="acct-mi"
                onClick={toggleShortcut}
              >
                <IconKey size={18} />
                <span className="acct-ml">The P shortcut</span>
                <span className="acct-sw" aria-hidden="true" />
              </button>
            </li>
            <li>
              <form method="post" action="/auth/logout">
                <button type="submit" className="acct-mi">
                  <IconSignOut size={18} />
                  Sign out
                </button>
              </form>
            </li>
          </ul>
        </div>
      ) : null}
      <button
        ref={button}
        type="button"
        className={placement === "up" ? "sb-me" : "ptop-me"}
        data-tip={placement === "up" ? data.name : undefined}
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((o) => !o)}
      >
        <Avatar initials={data.initials} size={36} tier={data.tier} ring="neutral" />
        {placement === "up" ? (
          <span className="sb-l sb-who" aria-hidden="true">
            <b>{data.name}</b>
            {tierLine ? <span>{tierLine}</span> : null}
          </span>
        ) : null}
      </button>
    </div>
  );
}
