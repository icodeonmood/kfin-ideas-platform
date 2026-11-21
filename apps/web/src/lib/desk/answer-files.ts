/**
 * S-R3's files on an answer (BLD-B275; DEC-124, C-FILE.row, L-QUESTIONS.answer/1): the plain rules, kept apart from
 * the screen so they are tested without a browser.
 *
 * - An answer's file is one of the idea's own files (purpose 'idea', BLD-B274): `POST /api/files` carries the answer's
 *   id and the file, never `for` ("conversation" is S-08's box, and the worker refuses it on an answer).
 * - An answer counts as answered with words or with a file the server holds, as the worker's `_has_content` and
 *   `send_answers` count it.
 * - "Check your answers" and the Sent list say what is attached in the Answer board's pattern: "Two screenshots
 *   attached, folio hidden." (reference/copy/Answer.md, state Sent).
 */
import type { ProofItem } from "@/app/share/[id]/check/model";
import type { AnswerFile, FileItem, SetQuestion } from "@/lib/contracts";

/** S-R3's words for the "+" and its rows. The name and tooltip are the Answer board's (Answer.md, PhoneAnswer.md: the
 * button "Attach files to this answer", its tooltip "Attach files"), through lane D's `label` and `tooltip`, because
 * S-R3's "+" opens files only (BLD-B275). The list's name is lane F's for S-08's box (`S08_COPY.files`), kept here so
 * S-R3 does not load S-08's module, and pinned equal to it by a test. */
export const ANSWER_FILES_COPY = {
  attach: "Attach files to this answer",
  attachTip: "Attach files",
  files: "Your files",
} as const;

/** The multipart body of `POST /api/files` for an answer (A-API.files): `answer_id` and `file`. Never `for`. */
export function answerUploadForm(answerId: string, file: File): FormData {
  const form = new FormData();
  form.append("answer_id", answerId);
  form.append("file", file, file.name);
  return form;
}

/** A row the server holds for the answer, in any state: the worker counts it as the answer's (`_files`). */
export function held(p: Pick<ProofItem, "item">): boolean {
  return Boolean(p.item?.id);
}

/** Answered: words, or a file the server holds (the worker's `_has_content`). */
export function isAnswered(text: string | undefined, rows: readonly ProofItem[] | undefined): boolean {
  return Boolean((text ?? "").trim()) || (rows ?? []).some(held);
}

/** An answer's file as the set's read gives it (`AnswerFile`), as the row's `FileItem`. */
export function answerFileItem(f: AnswerFile): FileItem {
  const item: Omit<FileItem, "added_by" | "added_at"> = {
    id: f.id,
    kind: f.kind as FileItem["kind"],
    name: f.name,
    type: f.type ?? "",
    size: f.size,
    pages: f.pages ?? undefined,
    state: (f.state ?? "checking") as FileItem["state"],
    hidden_note: f.hidden_note ?? undefined,
  };
  return item as FileItem;
}

/** The rows each unsent answer already has when the page opens, by question id. */
export function seedRows(questions: readonly SetQuestion[]): Record<string, ProofItem[]> {
  const out: Record<string, ProofItem[]> = {};
  for (const q of questions) {
    const files = q.answer && !q.answer.sent ? q.answer.files : [];
    if (files.length) {
      out[q.id] = files.map((f) => ({ key: `srv-${f.id}`, item: answerFileItem(f), name: f.name }));
    }
  }
  return out;
}

const COUNT_WORDS = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"];

type Attached = { type?: string | null; hidden_note?: string | null };

/**
 * "Two screenshots attached, folio hidden." (Answer.md): how many, "screenshot" when every file is an image and
 * "file" otherwise, and what the checks hid, from each file's own note ("Folio hidden"). Empty for no files.
 */
export function filesLine(files: readonly Attached[]): string {
  const n = files.length;
  if (!n) return "";
  const images = files.every((f) => (f.type ?? "").startsWith("image/"));
  const noun = `${images ? "screenshot" : "file"}${n === 1 ? "" : "s"}`;
  const hidden = Array.from(
    new Set(files.map((f) => (f.hidden_note ?? "").trim()).filter((h) => h.length > 0)),
  ).map((h) => h.charAt(0).toLowerCase() + h.slice(1));
  return `${COUNT_WORDS[n - 1] ?? String(n)} ${noun} attached${hidden.length ? `, ${hidden.join(", ")}` : ""}.`;
}

/** The files a row list holds on the server, for `filesLine`. */
export function attachedOf(rows: readonly ProofItem[] | undefined): Attached[] {
  return (rows ?? []).filter(held).map((p) => ({ type: p.item?.type, hidden_note: p.item?.hidden_note }));
}
