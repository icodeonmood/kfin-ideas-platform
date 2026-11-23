/** The voice lines Share (S-04) and Home (S-03) both draw, and the hook they both use to tell a phone, in a small
 * module of their own, so Home never loads the Share screen to read two lines (BLD-C232; from compose.tsx). */
import { useEffect, useState } from "react";

import { BANNERS } from "@/lib/killswitch-routes";

export const VOICE_COPY = {
  /** A note paused or unavailable: every voice-off line reads the same, the product lead's decision of 18 Nov (BLD-C149). */
  voicePaused: BANNERS["capture.voice"], // the voice-off line from the one source (BLD-157)
  /** A note that failed because the session ended: L-AUTH.states "Session expired mid-draft" (SignIn.md). */
  signInAgain: "Sign in again to carry on",
} as const;

/** C-PROMPT.voice, a note that failed (BLD-C127): signed out → the sign-in line; paused or unavailable → the paused
 * line; any other reason (no microphone, an old browser, audio suspended, too many this hour, a lost stream) has no
 * line in the pack, so nothing is invented and the mic is simply ready again (listed for HR). */
export function voiceFailedLine(reason: string): "sign_in" | "paused" | null {
  if (reason === "signed_out") return "sign_in";
  if (["paused", "unavailable", "voice_paused", "voice_unavailable"].includes(reason)) return "paused";
  return null;
}

/** A phone's layout (max-width 640px), as S-04 and S-03 draw it; false until the page has mounted. */
export function useIsPhone(): boolean {
  const [phone, setPhone] = useState(false);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return; // no media queries here (a test page): not a phone
    const mq = window.matchMedia("(max-width: 640px)");
    const on = () => setPhone(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return phone;
}
