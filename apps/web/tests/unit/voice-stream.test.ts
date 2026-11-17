import { describe, expect, it } from "vitest";

import { switchesFor } from "@/lib/killswitch-routes";
import policy from "@/lib/rbac.json";
import { isUuid, parseSeq, VOICE_MAX_CHUNK_BYTES, VOICE_NOTICE, VOICE_SAMPLE_RATE } from "@/lib/voice-stream";

const id = "11111111-2222-4333-8444-555555555555";

describe("BLD-C112 drafts by voice (DEC-108, L-DRAFT.voice)", () => {
  it("start, chunk and end need capture.voice, speech.hosted and submissions; reading a note does not", () => {
    for (const step of ["start", "chunk", "end"]) {
      expect(switchesFor("POST", `/api/drafts/${id}/voice/${step}`).sort()).toEqual(
        ["capture.voice", "speech.hosted", "submissions"].sort(),
      );
    }
    expect(switchesFor("GET", `/api/drafts/${id}/voice/${id}`)).toEqual([]);
    expect(switchesFor("GET", "/api/voice/config")).toEqual([]);
  });

  it("the sharer only (submit); the config for anyone signed in", () => {
    const endpoints = (policy as { endpoints: string[] }).endpoints.map((l) =>
      l.split(/\s+/).slice(0, 3).join(" "),
    );
    for (const e of [
      "POST /api/drafts/{id}/voice/start submit",
      "POST /api/drafts/{id}/voice/chunk submit",
      "POST /api/drafts/{id}/voice/end submit",
      "GET /api/drafts/{id}/voice/{stream} submit",
      "GET /api/voice/config signed_in",
    ])
      expect(endpoints).toContain(e);
  });

  it("chunks are numbered from 0 and stream ids are uuids", () => {
    expect(parseSeq("0")).toBe(0);
    expect(parseSeq("17")).toBe(17);
    for (const bad of [null, "", "-1", "1.5", "x", "1234567"]) expect(parseSeq(bad)).toBeUndefined();
    expect(isUuid(id)).toBe(true);
    expect(isUuid("../x")).toBe(false);
  });

  it("BLD-C116: the notice names no vendor; the browser sends 16 kHz PCM, at most 2 seconds a chunk", () => {
    expect(VOICE_NOTICE).toBe(
      "Your voice note goes to an Indian speech service to turn it into text. You can check the text before you send it.",
    );
    expect(VOICE_NOTICE.toLowerCase()).not.toContain("sarvam");
    expect(VOICE_SAMPLE_RATE).toBe(16_000);
    expect(VOICE_MAX_CHUNK_BYTES).toBe(2 * 16_000 * 2);
  });
});
