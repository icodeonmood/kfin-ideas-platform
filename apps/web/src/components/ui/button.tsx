"use client";

import Link from "next/link";
import {
  forwardRef,
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
 * Busy swaps the label for the action in progress ("Sending…") with a spinner and ignores further clicks; with a
 * busyLabel both labels share one cell, so the width never changes (C-BUTTON.states/5).
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
  const blocked = Boolean(disabled || busy);
  return (
    <button
      {...rest}
      ref={ref}
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
      {busyLabel !== undefined ? (
        // Both labels share one cell, so the button is always as wide as the wider one and never jumps when the
        // label changes; the one not showing is hidden from sight and from screen readers.
        <span className="btn-lbls">
          <span className="btn-lbl" aria-hidden={busy ? true : undefined}>
            {icon}
            {children}
          </span>
          <span className="btn-lbl" aria-hidden={busy ? undefined : true}>
            <span className="spin" aria-hidden="true" />
            {busyLabel}
          </span>
        </span>
      ) : (
        <>
          {busy ? <span className="spin" aria-hidden="true" /> : icon}
          {children}
        </>
      )}
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
