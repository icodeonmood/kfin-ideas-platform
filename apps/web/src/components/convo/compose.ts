/**
 * S-08's plain logic, kept apart from the screen so it is tested on its own: the words the screen owns, the @mention
 * picker's query, putting a picked name in the box, which mentions the words still carry, the highlighted names in a
 * message, an error's words and a file's lines. Everything the server words (lines, placeholders, visibility,
 * titles) comes in `ConversationView` and is shown as it is (A-API.conventions/6).
 */
import type { FileItem } from "@/lib/contracts";

type Person = { id: string; name: string; first_name: string; initials: string };

/** S-08's own words: the pack's (Messages.md), and lane F's where the pack draws none (docs/hr-wording/lane-f.md). */
export const S08_COPY = {
  heading: "Conversation",
  side: "In this conversation",
  /** Messages.md, while Teams is on (DEC-105). */
  sideNote:
    "This is the idea’s own conversation. It shows on the idea’s page too, and new messages reach you in your Inbox, on Teams and by email.",
  /** The same line without its Teams clause, while Teams is off (BLD-F086, for HR's sign-off). */
  sideNoteNoTeams:
    "This is the idea’s own conversation. It shows on the idea’s page too, and new messages reach you in your Inbox and by email.",
  send: "Send",
  sending: "Sending",
  empty: "Write a message or attach a file first.",
  answer: "Answer the questions",
  addedTo: "Added to",
  // Lane F's (not drawn by the pack):
  failed: "Your message didn’t send. Try again.",
  removeFailed: "The message wasn’t removed. Try again.",
  remove: "Remove",
  seeOnIdea: "See them on the idea",
  mentionList: "People to mention",
  people: "Who is in this conversation",
  close: "Close",
  view: "View",
  /** The name of the list of files in the box (S-08's "+", BLD-F095). On S-08 a link goes into the words, not into a
   * row, so it is not Home's "Your files and links". */
  files: "Your files",
  /** A file in the box with a customer detail found (DEC-107): the worker never sends it in the conversation
   * (`file_has_detail`), and S-08 has no way to hide the detail, so the row says so and offers Remove (BLD-F095).
   * Never Check it's "Only you, the review desk and the Ones Committee can open it.": that is about opening it. */
  fileHasDetail:
    "This file has a customer detail in it, so it can’t be sent in the conversation. Remove it to send your message.",
} as const;

/**
 * The side panel's last line names Teams only while Teams messages go out (DEC-105, BLD-F086). Only a `true` from the
 * server counts: a missing or other value never promises Teams.
 */
export function sideNote(teamsOn: unknown): string {
  return teamsOn === true ? S08_COPY.sideNote : S08_COPY.sideNoteNoTeams;
}

/** "1 person to mention. …" / "3 people to mention. …": announced when the list opens or narrows. */
export function mentionHint(n: number): string {
  if (n === 0) return "";
  return `${n} ${n === 1 ? "person" : "people"} to mention. Use the up and down arrows, then Enter.`;
}

export interface MentionQuery {
  /** Where the "@" is. */
  start: number;
  /** What follows it up to the caret. */
  query: string;
}

/** The "@…" being typed at the caret: an "@" at the start or after a space, with no line break before the caret. */
export function mentionAt(text: string, caret: number): MentionQuery | null {
  const before = text.slice(0, caret);
  const at = before.lastIndexOf("@");
  if (at < 0) return null;
  if (at > 0 && !/\s/.test(before[at - 1]!)) return null;
  const query = before.slice(at + 1);
  if (query.length > 40 || /[\n\r]/.test(query)) return null;
  return { start: at, query };
}

/** The people whose name or first name starts with the query, at most 6, the reader never among them. */
export function mentionChoices<P extends Person>(people: P[], query: string): P[] {
  const q = query.toLowerCase();
  return people
    .filter((p) => {
      const name = p.name.toLowerCase();
      return name.startsWith(q) || p.first_name.toLowerCase().startsWith(q) || name.includes(` ${q}`);
    })
    .slice(0, 6);
}

/** The box's words with "@Full Name " in place of the "@…" being typed, and where the caret goes. */
export function putMention(
  text: string,
  q: MentionQuery,
  caret: number,
  person: Person,
): { text: string; caret: number } {
  const inserted = `@${person.name} `;
  return {
    text: text.slice(0, q.start) + inserted + text.slice(caret),
    caret: q.start + inserted.length,
  };
}

/**
 * A link from the picker's link field, put into the words as it was typed (S-08's "+", BLD-F095): at the caret, or at
 * the end, with a space between it and the words either side. It is never fetched (non-negotiable 8) and is masked
 * with the rest of the message when it is sent (L-CONVO/7). Returns the words and where the caret goes, after it.
 */
export function putLink(
  text: string,
  caret: number | null | undefined,
  link: string,
): { text: string; caret: number } {
  const at = caret === null || caret === undefined || caret < 0 || caret > text.length ? text.length : caret;
  const before = text.slice(0, at);
  const after = text.slice(at);
  const lead = before && !/\s$/.test(before) ? " " : "";
  const tail = /^\s/.test(after) ? "" : " "; // so the next word typed is not joined to the link
  const put = `${lead}${link}${tail}`;
  return { text: before + put + after, caret: at + put.length };
}

/** The mentions the words still carry: a picked person whose "@Name" was deleted is not mentioned. */
export function mentionsIn(text: string, picked: ReadonlyMap<string, string>): string[] {
  return [...picked].filter(([, name]) => text.includes(`@${name}`)).map(([id]) => id);
}

/** A message's words split around each "@Name" it mentions, for the highlight (Messages.md, `.ment`). */
export function withMentions(text: string, names: string[]): { text: string; mention: boolean }[] {
  const tags = [...new Set(names.filter(Boolean).map((n) => `@${n}`))].sort((a, b) => b.length - a.length);
  if (!tags.length) return [{ text, mention: false }];
  const out: { text: string; mention: boolean }[] = [];
  let i = 0;
  let plain = "";
  while (i < text.length) {
    const tag = tags.find((t) => text.startsWith(t, i));
    if (tag) {
      if (plain) out.push({ text: plain, mention: false });
      out.push({ text: tag, mention: true });
      plain = "";
      i += tag.length;
    } else {
      plain += text[i];
      i += 1;
    }
  }
  if (plain) out.push({ text: plain, mention: false });
  return out;
}

/**
 * What to say when a write fails: the worker's message (`{ error: { code, message, field } }`), the proxy's banner
 * when writing is paused (`{ error: "paused", banner }`), or lane F's plain line.
 */
export function errorText(body: unknown, fallback: string = S08_COPY.failed): string {
  if (body && typeof body === "object") {
    const b = body as { error?: unknown; banner?: unknown };
    if (b.error && typeof b.error === "object") {
      const m = (b.error as { message?: unknown }).message;
      if (typeof m === "string" && m.trim()) return m;
    }
    if (typeof b.banner === "string" && b.banner.trim()) return b.banner;
  }
  return fallback;
}

/** "12 KB", "2.4 MB": a file's size as people read it. */
export function fileSize(bytes: number | undefined): string | undefined {
  if (bytes === undefined || !Number.isFinite(bytes) || bytes < 0) return undefined;
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(/\.0$/, "")} MB`;
}

/** C-FILE's status for a checked file: "Checked", or the note on what was hidden in it. */
export function fileStatus(f: FileItem): { status: "checked" | "hidden"; text: string } {
  if (f.state === "hidden_checked") return { status: "hidden", text: f.hidden_note || "Checked" };
  return { status: "checked", text: "Checked" };
}
