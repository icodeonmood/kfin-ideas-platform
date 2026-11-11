import { BANNERS, type SwitchName } from "@/lib/killswitch-routes";
import { switchStates } from "@/server/killswitch";

// Paused features everyone should know about; the rest only matter on the screens that use them.
const SHOWN: SwitchName[] = ["submissions", "attachments.upload", "wall.public", "ai.all"];

/** Plain-words banners for paused features (§7.6): the frosted band of the design system (DEC-099). Text, not colour, carries the message. */
export async function PausedBanners() {
  let states: Map<string, string>;
  try {
    states = await switchStates();
  } catch {
    return null;
  }
  const paused = SHOWN.filter((name) => states.get(name) !== "on");
  if (paused.length === 0) return null;
  return (
    <div className="banners" role="status">
      {paused.map((name) => (
        <p key={name} className="paused">
          <span className="paused-glyph" aria-hidden="true">
            <svg className="glyph" viewBox="0 0 20 20" focusable="false">
              <path d="M8 6.5v7M12 6.5v7" />
            </svg>
          </span>
          <span>{BANNERS[name]}</span>
        </p>
      ))}
    </div>
  );
}
