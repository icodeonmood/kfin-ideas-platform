import { NextResponse } from "next/server";

import {
  VOICE_EN_LABEL,
  VOICE_MAX_CHUNK_BYTES,
  VOICE_MAX_SECONDS,
  VOICE_NOTICE,
  VOICE_SAMPLE_RATE,
} from "@/lib/voice-stream";
import { signedIn } from "@/server/auth/authorize";
import { isOn, switchStates } from "@/server/killswitch";

/** GET /api/voice/config → what S-04 needs before the mic: whether voice is on, the notice shown before recording
 * (DEC-108 (5), no vendor name), the English copy's label and what the browser sends (BLD-C116). */
export async function GET() {
  const me = await signedIn();
  if (me instanceof NextResponse) return me;
  const states = await switchStates();
  return NextResponse.json({
    on: isOn(states, "capture.voice") && isOn(states, "speech.hosted"),
    notice: VOICE_NOTICE,
    en_label: VOICE_EN_LABEL,
    encoding: "pcm_s16le",
    sample_rate: VOICE_SAMPLE_RATE,
    channels: 1,
    chunk_seconds: 1,
    max_chunk_bytes: VOICE_MAX_CHUNK_BYTES,
    max_seconds: VOICE_MAX_SECONDS,
  });
}
