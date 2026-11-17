/**
 * The shell's line icons, taken from the design pack's boards (F-ICONS.style: 24 grid, round caps and joins, stroke
 * 1.8 for navigation, 2 for actions). Decorative: the link or button beside them carries the name.
 */
import type { ReactNode } from "react";

type Props = { size?: number; stroke?: number; className?: string };

function Svg({ size = 20, stroke = 1.8, className, children }: Props & { children: ReactNode }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const IconHome = (p: Props) => (
  <Svg {...p}>
    <path d="M4 11 12 4l8 7" />
    <path d="M6 10v9h12v-9" />
    <path d="M10 19v-5h4v5" />
  </Svg>
);

export const IconMyIdeas = (p: Props) => (
  <Svg {...p}>
    <path d="M9 7h11M9 12h11M9 17h11" />
    <circle cx="4.5" cy="7" r="1" />
    <circle cx="4.5" cy="12" r="1" />
    <circle cx="4.5" cy="17" r="1" />
  </Svg>
);

export const IconCrew = (p: Props) => (
  <Svg {...p}>
    <circle cx="9" cy="8" r="3" />
    <circle cx="17" cy="9.5" r="2.5" />
    <path d="M3.5 19c.6-3 2.8-5 5.5-5s4.9 2 5.5 5M14.5 14.6c.8-.4 1.6-.6 2.5-.6 2.2 0 3.9 1.6 4.4 4" />
  </Svg>
);

export const IconWall = (p: Props) => (
  <Svg {...p}>
    <rect x="4" y="4" width="7" height="7" rx="1.5" />
    <rect x="13" y="4" width="7" height="7" rx="1.5" />
    <rect x="4" y="13" width="7" height="7" rx="1.5" />
    <rect x="13" y="13" width="7" height="7" rx="1.5" />
  </Svg>
);

export const IconInbox = (p: Props) => (
  <Svg {...p}>
    <path d="M4 13.5 6.5 5h11l2.5 8.5V19H4z" />
    <path d="M4 13.5h4.5l1 2h5l1-2H20" />
  </Svg>
);

export const IconDesk = (p: Props) => (
  <Svg {...p}>
    <rect x="5" y="4" width="14" height="17" rx="2" />
    <path d="M9 4V3h6v1M9 10h6M9 14h6M9 18h3" />
  </Svg>
);

export const IconCommittee = (p: Props) => (
  <Svg {...p}>
    <path d="M12 3 5 6v5c0 4.4 3 8.3 7 9.5 4-1.2 7-5.1 7-9.5V6z" />
    <path d="m9 12 2 2 4-4" />
  </Svg>
);

export const IconPlus = (p: Props) => (
  <Svg stroke={2} {...p}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);

export const IconFold = (p: Props) => (
  <Svg {...p}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="3" />
    <path d="M9.5 4.5v15" />
    <path d="m15.5 10-2 2 2 2" />
  </Svg>
);

export const IconSearch = (p: Props) => (
  <Svg size={16} stroke={2} {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4.5 4.5" />
  </Svg>
);

export const IconBack = (p: Props) => (
  <Svg size={22} stroke={2} {...p}>
    <path d="m15 5-7 7 7 7" />
  </Svg>
);

export const IconSync = (p: Props) => (
  <Svg size={16} stroke={2} {...p}>
    <path d="M20 11a8 8 0 0 0-14.3-4.9L4 8" />
    <path d="M4 4v4h4" />
    <path d="M4 13a8 8 0 0 0 14.3 4.9L20 16" />
    <path d="M20 20v-4h-4" />
  </Svg>
);

export const IconTick = (p: Props) => (
  <Svg size={14} stroke={2.2} {...p}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </Svg>
);

export const IconAdmin = (p: Props) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </Svg>
);

export const IconSignOut = (p: Props) => (
  <Svg {...p}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="m16 17 5-5-5-5" />
    <path d="M21 12H9" />
  </Svg>
);

export const IconKey = (p: Props) => (
  <Svg {...p}>
    <rect x="3" y="6" width="18" height="12" rx="2" />
    <path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10" />
  </Svg>
);

export const IconEmber = (p: Props) => (
  <Svg {...p}>
    <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H17v15.5a.5.5 0 0 1-.5.5H6a2 2 0 0 1-2-2z" />
    <path d="M17 8h2.5a.5.5 0 0 1 .5.5V18a2 2 0 0 1-2 2" />
    <path d="M8 8h5M8 12h5M8 16h3" />
  </Svg>
);

export const IconDelivery = (p: Props) => (
  <Svg {...p}>
    <path d="M12 3 4 7v10l8 4 8-4V7z" />
    <path d="m4 7 8 4 8-4M12 11v10" />
  </Svg>
);

export const IconProfile = (p: Props) => (
  <Svg {...p}>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M5 21a7 7 0 0 1 14 0" />
  </Svg>
);

/** A One's dashboard (S-ONE): a gauge, the needle on the number. */
export const IconOne = (p: Props) => (
  <Svg {...p}>
    <path d="M4 17a8 8 0 1 1 16 0" />
    <path d="m12 17 3.5-5" />
    <circle cx="12" cy="17" r="1" />
  </Svg>
);

/** The sidebar and tab icon for a navigation key (policy/rbac.yaml `navigation:`). */
export function NavIcon({ navKey, ...p }: Props & { navKey: string }) {
  switch (navKey) {
    case "home":
      return <IconHome {...p} />;
    case "my-ideas":
      return <IconMyIdeas {...p} />;
    case "crew":
      return <IconCrew {...p} />;
    case "wall":
      return <IconWall {...p} />;
    case "inbox":
      return <IconInbox {...p} />;
    case "desk":
      return <IconDesk {...p} />;
    case "committee":
      return <IconCommittee {...p} />;
    case "share":
      return <IconPlus {...p} />;
    case "ember":
      return <IconEmber {...p} />;
    case "delivery":
      return <IconDelivery {...p} />;
    case "profile":
      return <IconProfile {...p} />;
    case "one":
      return <IconOne {...p} />;
    default:
      return <IconAdmin {...p} />;
  }
}
