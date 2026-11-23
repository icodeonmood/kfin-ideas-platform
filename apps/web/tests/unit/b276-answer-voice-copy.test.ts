// @vitest-environment jsdom
/**
 * C-PROMPT.voice, BLD-B276: S-R3's mic says what Share's box says, without loading Share's screen. Its lines for a
 * paused or signed-out note are COMPOSE_COPY's, and the reasons that draw them are Share's `voiceFailedLine`'s; the
 * helpers join the spoken words to the answer as typing would, and drop nothing heard.
 */
import { describe, expect, it } from "vitest";

import { COMPOSE_COPY, voiceFailedLine as shareLine } from "@/app/share/compose";
import {
  ANSWER_VOICE_COPY,
  answerVoiceBase,
  isSpeaking,
  spokenWords,
  voiceFailedLine,
  withSpoken,
} from "@/lib/desk/answer-voice";
import { MAX_ANSWER } from "@/lib/desk/answers";

describe("C-PROMPT.voice, BLD-B276: S-R3's voice words and joins", () => {
  it("BLD-B276: the paused and sign-in lines are Share's, word for word", () => {
    expect(ANSWER_VOICE_COPY.paused).toBe(COMPOSE_COPY.voicePaused);
    expect(ANSWER_VOICE_COPY.signInAgain).toBe(COMPOSE_COPY.signInAgain);
  });

  it("BLD-B276: every failure reason draws the line Share draws for it", () => {
    for (const reason of [
      "not_supported",
      "no_microphone",
      "signed_out",
      "stream_lost",
      "paused",
      "unavailable",
      "voice_paused",
      "voice_unavailable",
      "audio_suspended",
      "too_many",
    ])
      expect(voiceFailedLine(reason), reason).toBe(shareLine(reason));
  });

  it("S-R3, BLD-B276: a question's note goes to its own routes", () => {
    expect(answerVoiceBase("5c2f1e0a-7b3d-4e8f-9a1b-2c3d4e5f6a71")).toBe(
      "/api/questions/5c2f1e0a-7b3d-4e8f-9a1b-2c3d4e5f6a71/answer/voice",
    );
    expect(answerVoiceBase("a/b")).toBe("/api/questions/a%2Fb/answer/voice");
  });

  it("L-QUESTIONS.answer, BLD-B276: the words go after the answer with one space, and nothing heard is dropped", () => {
    expect(withSpoken("", "About fifteen a week.")).toBe("About fifteen a week.");
    expect(withSpoken("   ", "About fifteen.")).toBe("About fifteen.");
    expect(withSpoken("15 calls.\n", "Most on Mondays.")).toBe("15 calls. Most on Mondays.");
    expect(withSpoken("15 calls.", "  ")).toBe("15 calls.");
    const long = "a".repeat(MAX_ANSWER);
    expect(withSpoken(long, "and more")).toHaveLength(MAX_ANSWER + 9); // the counter and the worker's line say so
  });

  it("BLD-B276: which states are on their way, and which leave words for the box", () => {
    expect(["asking", "recording", "sending"].every((s) => isSpeaking(s as never))).toBe(true);
    expect(["idle", "blocked", "done", "paused", "failed"].some((s) => isSpeaking(s as never))).toBe(false);
    expect(spokenWords({ status: "failed", reason: "stream_lost", text: "About fifteen", spans: [] })).toBe(
      "About fifteen",
    );
    expect(
      spokenWords({
        status: "paused",
        banner: "",
        switchName: null,
        text: "About",
        spans: [],
        note: null,
      }),
    ).toBe("");
    expect(spokenWords({ status: "idle", notice: null })).toBe("");
  });
});
