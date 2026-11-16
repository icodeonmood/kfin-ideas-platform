"use client";

import Link from "next/link";
import {
  forwardRef,
  useLayoutEffect,
  useRef,
  type AnchorHTMLAttributes,
  type ButtonHTMLAttributes,
  type MouseEvent,
  type ReactNode,
} from "react";

/**
 * C-BUTTON. One ink primary per view (F-SPACE.cta/3), at the end of the flow; line for secondary actions, soft inside
 * cards, text for tertiary ones, blue text for links that open something related.
 *
 * Disabled is `aria-disabled`, never the `disabled` attribute: the button stays focusable so a screen reader finds it,
 * and a click calls `onDisabledClick` (C-BUTTON.states/4: move focus to the field that blocks it and show its message).
 * Busy swaps the label for the action in progress ("Sending…") with a spinner, keeps the button's width and ignores
 * further clicks (C-BUTTON.states/5).
 */
export type ButtonVariant = "primary" | "line" | "soft" | "text" | "text-blue";
export type ButtonSize = "regular" | "sm" | "full";

export function buttonClass(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "regular",
  extra?: string,
): string {
  const look =
    variant === "text"
      ? "tb"
      : variant === "text-blue"
        ? "tb blue"
        : `btn ${variant === "primary" ? "btn-primary" : variant === "line" ? "btn-secondary" : "btn-soft"}`;
  const sized =
    variant === "text" || variant === "text-blue"
      ? ""
      : size === "sm"
        ? "btn-sm"
        : size === "full"
          ? "btn-full"
          : "";
  return [look, sized, extra].filter(Boolean).join(" ");
}

type Common = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** A leading icon (16 to 18px, aria-hidden). */
  icon?: ReactNode;
};

export type ButtonProps = Common &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "disabled"> & {
    /** Shown as aria-disabled; the button stays focusable. */
    disabled?: boolean;
    onDisabledClick?: (e: MouseEvent<HTMLButtonElement>) => void;
    busy?: boolean;
    /** The action in progress, "Sending…". Defaults to the label. */
    busyLabel?: ReactNode;
  };

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "regular",
    icon,
    disabled,
    onDisabledClick,
    busy,
    busyLabel,
    className,
    onClick,
    children,
    type = "button",
    style,
    ...rest
  },
  ref,
) {
  const own = useRef<HTMLButtonElement | null>(null);
  const width = useRef<number | null>(null);

  // Keep the width the label had, so the button does not jump when the label changes to the busy one.
  useLayoutEffect(() => {
    const el = own.current;
    if (!el) return;
    if (busy) {
      if (width.current === null) width.current = el.getBoundingClientRect().width;
      el.style.minWidth = `${width.current}px`;
    } else {
      width.current = null;
      el.style.minWidth = "";
    }
  }, [busy]);

  const blocked = Boolean(disabled || busy);
  return (
    <button
      {...rest}
      ref={(el) => {
        own.current = el;
        if (typeof ref === "function") ref(el);
        else if (ref) ref.current = el;
      }}
      type={type}
      style={style}
      className={buttonClass(variant, size, className)}
      aria-disabled={disabled ? true : undefined}
      aria-busy={busy ? true : undefined}
      onClick={(e) => {
        if (busy) {
          e.preventDefault();
          return;
        }
        if (disabled) {
          e.preventDefault();
          onDisabledClick?.(e);
          return;
        }
        onClick?.(e);
      }}
      data-blocked={blocked ? "" : undefined}
    >
      {busy ? <span className="spin" aria-hidden="true" /> : icon}
      {busy ? (busyLabel ?? children) : children}
    </button>
  );
});

export type ButtonLinkProps = Common &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
    href: string;
  };

/** A link that looks like a button: for actions that go somewhere ("Save and close", "Open the full idea"). */
export function ButtonLink({
  variant = "primary",
  size = "regular",
  icon,
  className,
  children,
  href,
  ...rest
}: ButtonLinkProps) {
  return (
    <Link href={href} className={buttonClass(variant, size, className)} {...rest}>
      {icon}
      {children}
    </Link>
  );
}
