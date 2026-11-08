import { BANNERS, type SwitchName } from "@/lib/killswitch-routes";
import { switchStates } from "@/server/killswitch";

// Paused features everyone should know about; the rest only matter on the screens that use them.
const SHOWN: SwitchName[] = ["submissions", "attachments.upload", "wall.public", "ai.all"];

/** Plain-words banners for paused features (§7.6). Text, not colour, carries the message. */
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
        <p key={name} className="notice">
          {BANNERS[name]}
        </p>
      ))}
    </div>
  );
}
