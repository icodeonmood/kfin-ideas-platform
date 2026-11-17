/** S-R3 B3: an answer is never lost or misreported on a failed save (L-QUESTIONS.answer, V-FIELDS.answer/1). */
import { afterEach, describe, expect, it, vi } from "vitest";

import { putAnswer, SAVE_FAILED } from "@/lib/desk/answers";
import { BANNERS } from "@/lib/killswitch-routes";

const reply = (status: number, body: unknown) =>
  vi.fn(async () => new Response(JSON.stringify(body), { status }));

describe("S-R3 putAnswer", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("a saved answer reports the server's own text", async () => {
    vi.stubGlobal("fetch", reply(200, { id: "A-1", text: "Our Hyderabad branch alone.", sent: false }));
    expect(await putAnswer("Q-1", "Our Hyderabad branch alone. ")).toEqual({
      ok: true,
      text: "Our Hyderabad branch alone.",
    });
  });

  it("a dropped network shows Couldn’t save that. Try again., and is tried again", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    expect(await putAnswer("Q-1", "x")).toEqual({ ok: false, message: SAVE_FAILED, retry: true });
    expect(SAVE_FAILED).toBe("Couldn’t save that. Try again.");
  });

  it("a worker's refusal keeps its words and is not tried again", async () => {
    const e = { code: "answer_too_long", message: "Keep your answer under 2,000 characters.", field: "text" };
    vi.stubGlobal("fetch", reply(422, { error: e }));
    expect(await putAnswer("Q-1", "x")).toEqual({ ok: false, message: e.message, retry: false });
  });

  it("a paused feature shows its banner; a server error or a reply without text is the failure line", async () => {
    vi.stubGlobal(
      "fetch",
      reply(503, { error: "paused", switch: "submissions", banner: BANNERS.submissions }),
    );
    expect(await putAnswer("Q-1", "x")).toEqual({ ok: false, message: BANNERS.submissions, retry: true });
    vi.stubGlobal("fetch", reply(502, { error: { code: "desk_unavailable", message: "Worker text" } }));
    expect(await putAnswer("Q-1", "x")).toEqual({ ok: false, message: SAVE_FAILED, retry: true });
    vi.stubGlobal("fetch", reply(200, { id: "A-1" }));
    expect(await putAnswer("Q-1", "x")).toMatchObject({ ok: false, retry: true });
  });
});
