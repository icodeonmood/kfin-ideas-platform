/** Voice notes in quick capture (DEC-096): the recorder's words and helpers, and what it renders on and off. */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  announcement,
  failureMessage,
  formatElapsed,
  insertTranscript,
  leftOutMessage,
  MAX_SECONDS,
  pickMimeType,
  VOICE_COMING_SOON,
  VOICE_DONE,
  VOICE_HOW,
  VOICE_NEW,
  VOICE_START,
  VOICE_UNSUPPORTED,
} from "@/app/share/[id]/voice-logic";
import { VoiceRecorder } from "@/app/share/[id]/voice-recorder";

const esc = (text: string) => text.replaceAll("'", "&#x27;");
const render = (enabled: boolean) =>
  renderToStaticMarkup(createElement(VoiceRecorder, { ideaId: "x", enabled, onTranscript: () => undefined }));

describe("the recorder on screen", () => {
  it("off: says voice notes are coming soon and offers no button, with the line about improving them", () => {
    const html = render(false);
    expect(html).toContain(VOICE_COMING_SOON);
    expect(html).toContain(esc(VOICE_NEW));
    expect(html).not.toContain("<button");
  });

  it("on: one native button to start, how it works, and a polite live region", () => {
    const html = render(true);
    expect(html).toContain(`>${VOICE_START}</button>`);
    expect(html).toContain(esc(VOICE_HOW));
    expect(html).toContain(esc(VOICE_NEW));
    expect(html).toContain('role="status" aria-live="polite"');
    expect(html).toContain('role="group" aria-labelledby="voice-title"');
  });
});

describe("recorder helpers", () => {
  it("picks the first format the browser can record", () => {
    expect(pickMimeType((t) => t.startsWith("audio/mp4"))).toBe("audio/mp4");
    expect(pickMimeType((t) => t === "audio/webm;codecs=opus" || t === "audio/mp4")).toBe(
      "audio/webm;codecs=opus",
    );
    expect(pickMimeType(() => false)).toBe("");
  });

  it("shows the clock as m:ss and stops at 3 minutes", () => {
    expect(formatElapsed(5)).toBe("0:05");
    expect(formatElapsed(179.9)).toBe("2:59");
    expect(formatElapsed(MAX_SECONDS)).toBe("3:00");
  });

  it("speaks at the start, every 30 seconds, 10 seconds before the end and at the end; quiet otherwise", () => {
    expect(announcement(0)).toMatch(/^Recording\. You have up to 3 minutes\.$/);
    expect(announcement(30)).toBe("Recording, 30 seconds.");
    expect(announcement(90)).toBe("Recording, 1 minute 30 seconds.");
    expect(announcement(170)).toBe("10 seconds left.");
    expect(announcement(180)).toMatch(/stopped at 3 minutes/);
    const spoken = Array.from({ length: MAX_SECONDS + 1 }, (_, s) => announcement(s)).filter(Boolean);
    expect(spoken.length).toBeLessThanOrEqual(9);
  });

  it("adds the text after what is already in the box, never over it", () => {
    expect(insertTranscript("", "  Forms are typed twice. ")).toBe("Forms are typed twice.");
    expect(insertTranscript("Already here.\n", "And more.")).toBe("Already here.\n\nAnd more.");
    expect(insertTranscript("Keep me", "   ")).toBe("Keep me");
  });

  it("says plainly what was left out and why a note failed, never a code", () => {
    expect(leftOutMessage(0)).toBeNull();
    expect(leftOutMessage(1)).toBe("We left out 1 detail that looked like investor or customer data.");
    expect(leftOutMessage(2)).toMatch(/^We left out 2 details/);
    for (const code of ["voice_paused", "virus", "too_long", "nothing_heard", "unknown_thing", ""]) {
      const text = failureMessage(code);
      expect(text).not.toMatch(/_|\b(error|code|null|undefined)\b/i);
    }
    expect(failureMessage("voice_paused")).toMatch(/type it instead/);
    // DEC-096 review: the hourly limit has its own words; a refused codec or a broken file reads as unreadable.
    expect(failureMessage("too_many_this_hour")).toBe(
      "You've sent several voice notes in the last hour. Please wait a little, or type it instead.",
    );
    expect(failureMessage("codec_not_allowed")).toBe(failureMessage("type_not_allowed"));
    expect(failureMessage("unreadable")).toBe(failureMessage("type_not_allowed"));
    for (const code of ["too_many_this_hour", "codec_not_allowed", "fake_not_allowed", "engine_timeout"]) {
      expect(failureMessage(code)).not.toMatch(/_|\b(error|code|null|undefined)\b/i);
    }
  });

  it("uses the platform's words only", () => {
    for (const text of [
      VOICE_COMING_SOON,
      VOICE_DONE,
      VOICE_HOW,
      VOICE_NEW,
      VOICE_START,
      VOICE_UNSUPPORTED,
    ]) {
      expect(text).not.toMatch(/garage|duplicate|rejected|already solved|rant|sarvam/i);
    }
  });
});
