import { SparkMark } from "@/components/spark-mark";

/**
 * C-AVATAR: a disc with two initials. Sizes 44 (bars), 36 (sidebar foot, phone top row), 32 (crew faces) and 28 (tight
 * rows). A neutral ring by default where a ring is drawn; the tier ring only on the person's own account button,
 * Profile, the Wall, the One dashboard and the Ones cards (F-COLOR.tiers/1), which the caller decides.
 *
 * The disc is decorative when its name is already on screen beside it; otherwise pass `name` and it is announced.
 */
export type AvatarSize = 44 | 36 | 32 | 28;

export function Avatar({
  initials,
  size = 44,
  ring,
  tier,
  name,
  system,
  className,
}: {
  initials: string;
  size?: AvatarSize;
  /** "neutral" draws the grey ring; a tier (1 to 7) draws that tier's conic ring. */
  ring?: "neutral" | "none";
  tier?: number | null;
  /** The person's name, when nothing beside the avatar says it. */
  name?: string;
  /** A message from the 1% Club itself: the mark in place of initials (C-AVATAR.crew/3). */
  system?: boolean;
  className?: string;
}) {
  const ringClass =
    tier && tier >= 1 && tier <= 7 ? `av-ring av-t${tier}` : ring === "neutral" ? "av-ring" : "";
  const label = name ? { role: "img", "aria-label": name } : { "aria-hidden": true as const };
  return (
    <span
      className={["av", `av-${size}`, ringClass, system ? "av-sys" : "", className].filter(Boolean).join(" ")}
      {...label}
    >
      {system ? <SparkMark height={Math.round(size * 0.5)} /> : initials}
    </span>
  );
}

/** "Ravi Nair and 3 others on it", "4 colleagues on it", "Ravi Nair is on it". */
export function crewLine(people: Array<{ name: string }>, total = people.length, leadName?: string): string {
  if (total <= 0) return "Nobody on it yet";
  if (leadName) {
    const others = total - 1;
    if (others <= 0) return `${leadName} is on it`;
    return `${leadName} and ${others} ${others === 1 ? "other" : "others"} on it`;
  }
  return total === 1 ? "1 colleague on it" : `${total} colleagues on it`;
}

/**
 * C-AVATAR.crew: up to four faces overlapping by 8px, each with a white ring and a soft tint by position, then a line.
 * Each face can take focus and names its person in a small ink tooltip; the name is also what a screen reader hears.
 */
export function CrewFaces({
  people,
  total,
  leadName,
}: {
  people: Array<{ name: string; initials: string }>;
  /** Everyone on the crew, when more than the four faces shown. */
  total?: number;
  /** Lead with the lead's name ("Ravi Nair and 3 others on it"). */
  leadName?: string;
}) {
  const shown = people.slice(0, 4);
  return (
    <div className="crew">
      <span className="crew-faces">
        {shown.map((p, i) => (
          <span
            key={`${p.initials}-${i}`}
            className={`crew-face t${i + 1}`}
            tabIndex={0}
            role="img"
            aria-label={p.name}
            data-name={p.name}
          >
            <span aria-hidden="true">{p.initials}</span>
          </span>
        ))}
      </span>
      <span className="crew-l">{crewLine(people, total ?? people.length, leadName)}</span>
    </div>
  );
}
