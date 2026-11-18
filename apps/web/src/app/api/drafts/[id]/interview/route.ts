import { NextResponse, type NextRequest } from "next/server";

import { IDEMPOTENCY_HEADER } from "@/lib/contracts/api";
import { authorize } from "@/server/auth/authorize";
import {
  bodyOf,
  deviceOf,
  DraftApiError,
  draftError,
  drafts,
  noStore,
  spansForBrowser,
  UUID,
} from "@/server/drafts";
import {
  builtSinceAnswers,
  inAlternative,
  INTERVIEW_QUESTIONS,
  interviewPlace,
  logFlagEvent,
  nextQuestion,
  ownDraft,
  waitingToBuild,
  type InterviewPlace,
  type InterviewQuestion,
} from "@/server/flag-events";

const SCREEN = "S-04B";

const isQuestion = (v: unknown): v is InterviewQuestion =>
  typeof v === "string" && (INTERVIEW_QUESTIONS as readonly string[]).includes(v);

/**
 * POST /api/drafts/{id}/interview — flag S1 "Interview" (P-DECISIONS.experiments, L-DRAFT.parts/10; BLD-C172).
 *
 *   `{ action: "start" }`                      the questions begin, after the first telling
 *   `{ action: "answer", question, text }`     an answer, with the Idempotency-Key the message keeps on every try
 *   `{ action: "skip", question }`             "Skip this one"
 *   `{ action: "finish" }`                     the person moved on before the last question
 *
 * An answer goes into the draft exactly like the person's own words, through the worker's messages path, so it is
 * hidden and sealed like any message (DEC-103, L-HIDE); it is kept without building (`defer_run`). Once the last
 * question is answered or skipped, or the person moves on, the draft is built once (`/runs`), if anything was
 * answered. Each step is logged once per draft as a code (flag_events): that is the interview's place, so a reload or
 * another device carries on where the person was. A step that cannot be logged answers 503 (`save_failed`), and the
 * client's retry with the same Idempotency-Key keeps the answer once. `200 { interview, run_id, draft?, message? }`. Only for the
 * person's own draft, and only while they are in the alternative; "finish" works whatever the flag says now, so
 * answers never wait for a build that will not come.
 */
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const id = (await params).id;
  const body = await bodyOf(request);
  const device = deviceOf(request);
  const path = encodeURIComponent(id);
  try {
    if (!UUID.test(id) || !(await ownDraft(me.contributorCode, id)))
      throw new DraftApiError(404, "not_found");
    const action = body.action;
    // Lane A's reader decides (BLD-A216); this asks without logging an exposure (the page logged it).
    const variant = (await inAlternative(me.id, "s1")) ? "alternative" : "default";
    if (action !== "finish" && variant !== "alternative") throw new DraftApiError(409, "not_in_interview");
    const place: InterviewPlace = await interviewPlace(me.id, id);
    // A step that cannot be kept (and is not there already) answers 503: the client tries again with the same
    // Idempotency-Key, so the answer is kept once and the place is never lost (BLD-C172).
    const step = async (event: string, outcome: string) => {
      const kept = await logFlagEvent({
        userId: me.id,
        key: "s1",
        variant,
        event,
        outcome,
        screen: SCREEN,
        draftId: id,
      });
      if (kept === "failed") throw new DraftApiError(503, "save_failed");
    };

    /** The one build once the questions are over (only if an answer is waiting), then the end, logged once. */
    /** The one build, then the end. If the end cannot be logged (503), the retry finds the draft already built since
     * the last answer and only logs the end: the draft is built once (BLD-C172). */
    const end = async (outcome: "finished" | "left"): Promise<string | null> => {
      let runId: string | null = null;
      if (waitingToBuild(place) && !(await builtSinceAnswers(id))) {
        try {
          const { body: built } = await drafts.write(me, device, "POST", `${path}/runs`);
          runId =
            typeof (built as { run_id?: unknown })?.run_id === "string"
              ? (built as { run_id: string }).run_id
              : null;
        } catch (err) {
          // With the assistant paused every part is filled by hand (DEC-105): nothing to build, the interview ends.
          if (!(err instanceof DraftApiError && err.code === "assistant_off")) throw err;
        }
      }
      await step("s1.end", outcome);
      place.ended = outcome;
      return runId;
    };
    const fresh = async () => (await drafts.get(me, device, id, false)).body;

    if (action === "start") {
      if (!place.started) {
        await step("s1.start", "started");
        place.started = true;
      }
      return NextResponse.json({ interview: place, run_id: null }, { headers: noStore });
    }

    if (action === "finish") {
      if (!place.started || place.ended)
        return NextResponse.json({ interview: place, run_id: null }, { headers: noStore });
      const runId = await end("left");
      return NextResponse.json(spansForBrowser({ interview: place, run_id: runId, draft: await fresh() }), {
        headers: noStore,
      });
    }

    if (action !== "answer" && action !== "skip") throw new DraftApiError(400, "action_invalid");
    const q = body.question;
    if (!isQuestion(q)) throw new DraftApiError(400, "question_invalid");
    let message: unknown;
    let draft: unknown;
    if (!place.started && !place.ended) {
      // The start did not reach us (offline at the time): the first answer starts it.
      await step("s1.start", "started");
      place.started = true;
    }
    // Sent before (a retry), or the interview is over: nothing more to keep for this question.
    if (place.started && !place.ended && !place.done[q]) {
      if (action === "answer") {
        const { body: out } = await drafts.write(me, device, "POST", `${path}/messages`, {
          text: body.text,
          via: "typed",
          defer_run: true,
          client_id: request.headers.get(IDEMPOTENCY_HEADER) ?? undefined,
        });
        message = (out as { message?: unknown }).message;
        draft = (out as { draft?: unknown }).draft;
      }
      await step(`s1.${q}`, action === "answer" ? "answered" : "skipped");
      place.done[q] = action === "answer" ? "answered" : "skipped";
    }

    // The last one answered or skipped (now, or on a try whose build did not go): the draft is built once.
    let runId: string | null = null;
    if (place.started && !place.ended && nextQuestion(place) === null) {
      runId = await end("finished");
      draft = await fresh();
    }
    return NextResponse.json(
      spansForBrowser({
        interview: place,
        run_id: runId,
        ...(draft ? { draft } : {}),
        ...(message ? { message } : {}),
      }),
      { headers: noStore },
    );
  } catch (err) {
    return draftError(err);
  }
}
