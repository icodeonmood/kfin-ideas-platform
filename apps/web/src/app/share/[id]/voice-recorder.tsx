"use client";

/**
 * Voice notes in quick capture (DEC-096). The person records up to 3 minutes, can play it back, record again or
 * delete it, then "Turn it into text". The recording goes to quarantine, the worker scans it and turns it into
 * text, and the text lands in the box for the person to correct. Their browser then deletes the held text; the
 * server has already deleted the recording.
 *
 * Accessibility: native buttons only, focus moves to "Stop recording" when recording starts and to the next step
 * after, the clock is visible but quiet, and a polite live region speaks at the start, every 30 seconds, near the
 * end and at each step. No waveform or animation.
 */
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import {
  announcement,
  AUDIO_BITS_PER_SECOND,
  failureMessage,
  formatElapsed,
  leftOutMessage,
  MAX_SECONDS,
  pickMimeType,
  POLL_MS,
  VOICE_COMING_SOON,
  VOICE_DONE,
  VOICE_HOW,
  VOICE_NEW,
  VOICE_START,
  VOICE_TITLE,
  VOICE_UNSUPPORTED,
} from "./voice-logic";

type Step = "idle" | "recording" | "recorded" | "sending" | "done" | "error";

const noSubscription = () => () => {};
const browserCanRecord = () =>
  typeof window.MediaRecorder !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);

export function VoiceRecorder(p: { ideaId: string; enabled: boolean; onTranscript: (text: string) => void }) {
  const [step, setStep] = useState<Step>("idle");
  const [seconds, setSeconds] = useState(0);
  const [say, setSay] = useState("");
  const [note, setNote] = useState<{ text: string; error: boolean } | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const supported = useSyncExternalStore(noSubscription, browserCanRecord, () => true);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const blob = useRef<Blob | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const stopRef = useRef<HTMLButtonElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const startRef = useRef<HTMLButtonElement>(null);
  const cancelled = useRef(false);
  // Where focus goes once the next step has rendered (never on first load): set by an action, used once.
  const focusNext = useRef<"stop" | "next" | "start" | null>(null);

  useEffect(() => {
    const target = { stop: stopRef, next: nextRef, start: startRef }[focusNext.current ?? "start"];
    if (focusNext.current && target.current) {
      target.current.focus();
      focusNext.current = null;
    }
  }, [step]);

  useEffect(
    () => () => {
      cancelled.current = true;
      if (timer.current) clearInterval(timer.current);
      stream.current?.getTracks().forEach((t) => t.stop());
    },
    [],
  );

  useEffect(() => () => void (audioUrl && URL.revokeObjectURL(audioUrl)), [audioUrl]);

  function release() {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  }

  async function start() {
    setNote(null);
    let media: MediaStream;
    try {
      media = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setStep("error");
      setNote({ text: failureMessage("microphone_blocked"), error: true });
      return;
    }
    stream.current = media;
    const mimeType = pickMimeType((t) => MediaRecorder.isTypeSupported(t));
    const rec = new MediaRecorder(media, {
      ...(mimeType ? { mimeType } : {}),
      audioBitsPerSecond: AUDIO_BITS_PER_SECOND,
    });
    chunks.current = [];
    rec.ondataavailable = (e) => {
      if (e.data.size) chunks.current.push(e.data);
    };
    rec.onstop = () => {
      release();
      blob.current = new Blob(chunks.current, { type: rec.mimeType || mimeType || "audio/webm" });
      setAudioUrl(URL.createObjectURL(blob.current));
      setStep("recorded");
      focusNext.current = "next";
    };
    recorder.current = rec;
    rec.start(1000);
    setSeconds(0);
    setSay(announcement(0) ?? "");
    setStep("recording");
    focusNext.current = "stop";
    const began = Date.now();
    timer.current = setInterval(() => {
      const s = Math.min(MAX_SECONDS, Math.floor((Date.now() - began) / 1000));
      setSeconds(s);
      const words = announcement(s);
      if (words) setSay(words);
      if (s >= MAX_SECONDS) stop();
    }, 250);
  }

  function stop() {
    if (recorder.current?.state === "recording") recorder.current.stop();
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  }

  function discard(message: string) {
    blob.current = null;
    setAudioUrl(null);
    setStep("idle");
    setSay(message);
    focusNext.current = "start";
  }

  async function send() {
    if (!blob.current) return;
    setStep("sending");
    setSay("Turning your voice note into text. This takes a few seconds.");
    const form = new FormData();
    form.set("file", blob.current, "voice-note");
    const res = await fetch(`/api/submissions/${p.ideaId}/voice`, { method: "POST", body: form }).catch(
      () => null,
    );
    const body = (await res?.json().catch(() => null)) as { id?: string; error?: string } | null;
    // A 503 is a pause (the proxy says "paused", the worker "voice_paused"): either way, voice notes are paused.
    if (res?.status !== 201 || !body?.id)
      return fail(res?.status === 503 ? "voice_paused" : (body?.error ?? ""));
    const path = `/api/submissions/${p.ideaId}/voice/${body.id}`;
    const deadline = Date.now() + 5 * 60_000;
    while (!cancelled.current && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, POLL_MS));
      const s = await fetch(path, { cache: "no-store" }).catch(() => null);
      if (!s?.ok) continue;
      const v = (await s.json()) as {
        state: string;
        failure?: string;
        transcript?: string;
        removed_count?: number;
      };
      if (v.state === "ready" && typeof v.transcript === "string") {
        p.onTranscript(v.transcript);
        await fetch(path, { method: "DELETE" }).catch(() => null); // the text is in the box now
        blob.current = null;
        setAudioUrl(null);
        const extra = leftOutMessage(v.removed_count ?? 0);
        const done = extra ? `${VOICE_DONE} ${extra}` : VOICE_DONE;
        setNote({ text: done, error: false });
        setSay(done);
        setStep("done");
        focusNext.current = "start";
        return;
      }
      if (v.state === "failed" || v.state === "deleted") return fail(v.failure ?? "");
    }
    fail("");
  }

  function fail(code: string) {
    const text = failureMessage(code);
    setNote({ text, error: true });
    setSay(text);
    setStep(blob.current && code !== "virus" ? "recorded" : "error");
  }

  return (
    <div className="field voice-note" role="group" aria-labelledby="voice-title" aria-describedby="voice-new">
      <h3 id="voice-title">{VOICE_TITLE}</h3>
      {!p.enabled ? (
        <p>{VOICE_COMING_SOON}</p>
      ) : !supported ? (
        <p>{VOICE_UNSUPPORTED}</p>
      ) : (
        <>
          <p className="hint" id="voice-how">
            {VOICE_HOW}
          </p>
          {step === "recording" ? (
            <div className="voice-controls">
              <p className="voice-clock" role="timer" aria-live="off">
                Recording {formatElapsed(seconds)} of {formatElapsed(MAX_SECONDS)}
              </p>
              <button type="button" className="button" ref={stopRef} onClick={stop}>
                Stop recording
              </button>
            </div>
          ) : step === "recorded" || step === "sending" ? (
            <div className="voice-controls">
              {audioUrl ? (
                // The person's own words, played back only to them: no captions needed.
                <audio controls src={audioUrl} aria-label="Play back your voice note" />
              ) : null}
              <button
                type="button"
                className="button"
                ref={nextRef}
                onClick={() => void send()}
                disabled={step === "sending"}
              >
                {step === "sending" ? "Turning it into text…" : "Turn it into text"}
              </button>
              <button
                type="button"
                className="link-button"
                onClick={() => void start()}
                disabled={step === "sending"}
              >
                Record again
              </button>
              <button
                type="button"
                className="link-button"
                onClick={() => discard("Your voice note is deleted.")}
                disabled={step === "sending"}
              >
                Delete
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="button button-secondary"
              ref={startRef}
              onClick={() => void start()}
            >
              {step === "done" ? "Record another voice note" : VOICE_START}
            </button>
          )}
          {note ? <p className={note.error ? "field-error" : "muted"}>{note.text}</p> : null}
        </>
      )}
      <p className="hint" id="voice-new">
        {VOICE_NEW}
      </p>
      <p className="visually-hidden" role="status" aria-live="polite">
        {say}
      </p>
    </div>
  );
}
