/** BLD-B275, S-R3, C-FILE.row, L-QUESTIONS.answer: the plain rules behind the "+" on an answer. Synthetic data only. */
import { describe, expect, it } from "vitest";

import type { ProofItem } from "@/app/share/[id]/check/model";
import { S08_COPY } from "@/components/convo/compose";
import type { AnswerFile, SetQuestion } from "@/lib/contracts";
import {
  ANSWER_FILES_COPY,
  answerFileItem,
  answerUploadForm,
  attachedOf,
  filesLine,
  isAnswered,
  seedRows,
} from "@/lib/desk/answer-files";

const file = (over: Partial<AnswerFile> = {}): AnswerFile => ({
  id: "F-1",
  kind: "file",
  name: "sms-screenshot.png",
  type: "image/png",
  size: 2048,
  pages: null,
  state: "checked",
  hidden_note: null,
  customer_detail: false,
  ...over,
});

const row = (over: Partial<ProofItem> = {}): ProofItem => ({
  key: "k1",
  item: answerFileItem(file()),
  name: "sms-screenshot.png",
  ...over,
});

describe("BLD-B275 S-R3 answerUploadForm (A-API.files)", () => {
  it("carries the answer's id and the file, and never `for` (an answer's file is the idea's own, BLD-B274)", () => {
    const f = new File(["Calls about R07: 40 a day."], "branch-call-log.md", { type: "text/markdown" });
    const form = answerUploadForm("A-1", f);
    expect(form.get("answer_id")).toBe("A-1");
    expect((form.get("file") as File).name).toBe("branch-call-log.md");
    expect(form.has("for")).toBe(false);
    expect(form.has("idea_id")).toBe(false);
    expect(form.has("draft_id")).toBe(false);
    expect(Array.from(form.keys()).sort()).toEqual(["answer_id", "file"]);
  });
});

describe("BLD-B275 L-QUESTIONS.answer isAnswered (the worker's _has_content)", () => {
  it("words alone, or a file the server holds alone, count as answered", () => {
    expect(isAnswered("Our Hyderabad branch alone.", [])).toBe(true);
    expect(isAnswered("", [row()])).toBe(true);
    expect(isAnswered("   ", [row({ item: answerFileItem(file({ state: "personal_data_found" })) })])).toBe(
      true,
    );
  });

  it("nothing, spaces, or a file that never reached the server do not", () => {
    expect(isAnswered("", [])).toBe(false);
    expect(isAnswered(undefined, undefined)).toBe(false);
    expect(isAnswered("  \n", [row({ item: null, localState: "uploading" })])).toBe(false);
    expect(isAnswered("", [row({ item: null, localState: "too_big" })])).toBe(false);
  });
});

describe("BLD-B275 C-FILE.row seedRows", () => {
  it("seeds the rows of each unsent answer from the set's own files, and none for a sent answer", () => {
    const q = (id: string, sent: boolean, files: AnswerFile[]) =>
      ({
        id,
        seq: 1,
        part: "evidence",
        part_name: "Attached",
        text: "Can you add a screenshot of the SMS, with the folio hidden?",
        suggested: false,
        answer: {
          id: `A-${id}`,
          question_id: id,
          text: "",
          files,
          by: null,
          at: null,
          added_to: "evidence",
          added_to_name: "Attached",
          saved_at: null,
          sent_at: null,
          sent,
        },
      }) as unknown as SetQuestion;
    const seeded = seedRows([
      q("Q-1", false, [file()]),
      q("Q-2", true, [file({ id: "F-2" })]),
      q("Q-3", false, []),
    ]);
    expect(Object.keys(seeded)).toEqual(["Q-1"]);
    expect(seeded["Q-1"]![0]).toMatchObject({ key: "srv-F-1", name: "sms-screenshot.png" });
    expect(seeded["Q-1"]![0]!.item).toMatchObject({ id: "F-1", state: "checked", type: "image/png" });
  });
});

describe('BLD-B275 S-R3 filesLine (Answer.md: "Two screenshots attached, folio hidden.")', () => {
  it("draws the board's line", () => {
    expect(
      filesLine([
        { type: "image/png", hidden_note: "Folio hidden" },
        { type: "image/jpeg", hidden_note: "Folio hidden" },
      ]),
    ).toBe("Two screenshots attached, folio hidden.");
  });

  it("counts in words, says file for anything but images, and names nothing hidden when nothing was", () => {
    expect(filesLine([{ type: "text/markdown" }])).toBe("One file attached.");
    expect(filesLine([{ type: "image/png" }, { type: "application/pdf" }])).toBe("Two files attached.");
    expect(filesLine([{ type: "image/png" }])).toBe("One screenshot attached.");
    expect(filesLine([])).toBe("");
    expect(filesLine(Array.from({ length: 11 }, () => ({ type: "application/pdf" })))).toBe(
      "11 files attached.",
    );
  });

  it("reads only the rows the server holds", () => {
    expect(filesLine(attachedOf([row(), row({ key: "k2", item: null, localState: "upload_failed" })]))).toBe(
      "One screenshot attached.",
    );
  });
});

describe("BLD-B275 S-R3 ANSWER_FILES_COPY", () => {
  it("the list's name is lane F's for S-08's box, word for word", () => {
    expect(ANSWER_FILES_COPY.files).toBe(S08_COPY.files);
  });

  it('the "+" takes the Answer board\'s name and tooltip (Answer.md, PhoneAnswer.md)', () => {
    expect(ANSWER_FILES_COPY.attach).toBe("Attach files to this answer");
    expect(ANSWER_FILES_COPY.attachTip).toBe("Attach files");
  });
});
