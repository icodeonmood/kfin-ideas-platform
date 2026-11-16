/**
 * C-AVATAR: a disc with two initials. Sizes 44 (bars), 36 (sm: sidebar foot, phone top row), 32 (crew faces) and 28
 * (tight rows). A neutral ring by default where a ring is drawn; the tier ring only on the person's own account
 * button, Profile, the Wall, the One dashboard and the Ones cards (F-COLOR.tiers/1), which the caller decides.
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
  className,
}: {
  initials: string;
  size?: AvatarSize;
  /** "neutral" draws the grey ring; a tier (1 to 7) draws that tier's conic ring. */
  ring?: "neutral" | "none";
  tier?: number | null;
  /** The person's name, when nothing beside the avatar says it. */
  name?: string;
  className?: string;
}) {
  const ringClass =
    tier && tier >= 1 && tier <= 7 ? `av-ring av-t${tier}` : ring === "neutral" ? "av-ring" : "";
  const label = name ? { role: "img", "aria-label": name } : { "aria-hidden": true as const };
  return (
    <span className={["av", `av-${size}`, ringClass, className].filter(Boolean).join(" ")} {...label}>
      {initials}
    </span>
  );
}
