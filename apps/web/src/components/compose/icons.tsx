/**
 * Line icons for Tell it (C-PROMPT, C-DRAFT-PANEL, C-HIDDEN), path for path from the prototype boards
 * (reference/prototype/Compose.dc.html, ComposeResume.dc.html). Decorative: the control beside each one carries the
 * name. The shell's own icons stay in components/shell/icons.tsx.
 */
type Props = { size?: number; className?: string };

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
};

export const IconMic = ({ size = 20, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={1.9} {...base}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" />
  </svg>
);

export const IconMicOff = ({ size = 18, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 20 20" strokeWidth={1.7} {...base}>
    <rect x="7" y="2.5" width="6" height="10" rx="3" />
    <path d="M4.5 9.5a5.5 5.5 0 0 0 11 0M10 15v2.5M3 3l14 14" />
  </svg>
);

export const IconWave = ({ size = 22, className }: Props) => (
  <svg
    className={className}
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden
    focusable={false}
  >
    <rect x="3" y="9" width="2.4" height="6" rx="1.2" />
    <rect x="7.6" y="5.5" width="2.4" height="13" rx="1.2" />
    <rect x="12.2" y="8" width="2.4" height="8" rx="1.2" />
    <rect x="16.8" y="4" width="2.4" height="16" rx="1.2" />
    <rect x="21" y="10" width="2" height="4" rx="1" />
  </svg>
);

export const IconArrowUp = ({ size = 20, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={2.2} {...base}>
    <path d="M12 19V5M6 11l6-6 6 6" />
  </svg>
);

export const IconStop = ({ size = 16, className }: Props) => (
  <svg
    className={className}
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden
    focusable={false}
  >
    <rect x="5" y="5" width="14" height="14" rx="3" />
  </svg>
);

export const IconLock = ({ size = 18, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={2} {...base}>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </svg>
);

export const IconChevron = ({ size = 18, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={2} {...base}>
    <path d="M6 9l6 6 6-6" />
  </svg>
);

export const IconPencil = ({ size = 14, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={2} {...base}>
    <path d="M4 20h4L19 9l-4-4L4 16z" />
  </svg>
);

export const IconDevice = ({ size = 18, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 20 20" strokeWidth={1.6} {...base}>
    <rect x="6" y="2.5" width="8" height="15" rx="2" />
    <path d="M9 15h2" />
  </svg>
);

/** The boards draw only the phone (ComposeResume.dc.html's "Picked up" banner). A laptop is Lucide's laptop-minimal,
 * the library F-ICONS.style/6 says the set matches, drawn in the phone's 20px frame and stroke (BLD-C185). */
export const IconLaptop = ({ size = 18, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 20 20" strokeWidth={1.6} {...base}>
    <rect x="2.5" y="3.5" width="15" height="10" rx="1.7" />
    <path d="M1.7 16.5h16.6" />
  </svg>
);

export const IconMail = ({ size = 18, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 20 20" strokeWidth={1.6} {...base}>
    <rect x="2.5" y="4.5" width="15" height="11" rx="2" />
    <path d="m3 5.5 7 5.5 7-5.5" />
  </svg>
);

/** The three starters' marks on Home and the empty Tell it: a call, a loop, two screens. */
export const IconCall = ({ size = 18, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={1.8} {...base}>
    <path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1" />
  </svg>
);

export const IconLoop = ({ size = 18, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={1.8} {...base}>
    <path d="M4 12a8 8 0 0 1 14-5.3L20 9" />
    <path d="M20 4v5h-5" />
    <path d="M20 12a8 8 0 0 1-14 5.3L4 15" />
    <path d="M4 20v-5h5" />
  </svg>
);

export const IconScreens = ({ size = 18, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={1.8} {...base}>
    <rect x="3" y="5" width="12" height="14" rx="2" />
    <rect x="9" y="3" width="12" height="14" rx="2" />
  </svg>
);

/** C-PROMPT.attach: the subtle "+" (DEC-124), in place of the board's paperclip. */
export const IconPlus = ({ size = 20, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={1.9} {...base}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

/** A file row's remove (Home.md, `attachments`: "Remove {name}"). */
export const IconClose = ({ size = 14, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={2.2} {...base}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);

/** C-FILE.uploader/2: "Choose a folder". */
export const IconFolder = ({ size = 20, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={1.8} {...base}>
    <path d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4.6l2 2h8.4A1.5 1.5 0 0 1 21 9.5v8A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5z" />
  </svg>
);

/** The link field in the picker (Home.md, `attachments=Picker open`). */
export const IconLink = ({ size = 16, className }: Props) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" strokeWidth={1.9} {...base}>
    <path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1" />
    <path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1" />
  </svg>
);
