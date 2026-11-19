/**
 * C-HIDDEN and L-HIDE on the front end (S-04, S-04B; BLD-C121): the person's own words stay exactly as typed, with a
 * dotted underline under each detected detail; everything else shows only the masked form ("Folio ••••89").
 */
import {
  SHOW_REASON_LABEL,
  type HiddenDetail,
  type HiddenKind,
  type HiddenSpan,
  type ShowReason,
} from "@/lib/contracts";

/** L-HIDE.detect "Kind" column, for the folded bar's line ("Folio number, PAN and phone number"). */
const KIND_NAME: Record<HiddenKind, string> = {
  folio: "Folio number",
  pan: "PAN",
  phone: "Phone number",
  email: "Email address",
  account: "Bank account",
  aadhaar: "Aadhaar number",
  name: "Customer name",
};

/** L-HIDE.detect "Label shown" column: the short kind on each row of the open list. */
export const KIND_LABEL: Record<HiddenKind, string> = {
  folio: "Folio",
  pan: "PAN",
  phone: "Phone",
  email: "Email",
  account: "Account",
  aadhaar: "Aadhaar",
  name: "Name",
};

const KEEP_CASE = new Set<HiddenKind>(["pan", "aadhaar"]);

/** A word naming a kind, then (after a space, or ": ", "# " or "- ") that kind's masked form ("folio Folio ••••17",
 * "PAN: PAN ••••8Z"). With the `i` flag the back-reference matches in any case. */
const NAMED_TWICE = new RegExp(`\\b(${Object.values(KIND_LABEL).join("|")})[\\s:#-]*\\s(?=\\1 •)`, "gi");

/**
 * The masked copy of a person's words, as lane C's screens show it in a quote (BLD-C193): where the word typed just
 * before a masked detail is that detail's own label, the label is said once ("one investor with folio Folio ••••17"
 * reads "one investor with Folio ••••17"). Display only: the masked form L-HIDE makes, what is stored and what
 * anyone else receives are untouched, and nothing is unmasked; only the repeated word goes.
 */
export function labelOnce(text: string): string {
  return text.replace(NAMED_TWICE, "");
}

/** "Folio number, PAN and phone number": each kind once, in the order found; later ones in lower case. */
export function kindsLine(details: Pick<HiddenDetail, "kind">[]): string {
  const kinds: HiddenKind[] = [];
  for (const d of details) if (!kinds.includes(d.kind)) kinds.push(d.kind);
  const names = kinds.map((k, i) => {
    const name = KIND_NAME[k] ?? k;
    return i === 0 || KEEP_CASE.has(k) ? name : name.charAt(0).toLowerCase() + name.slice(1);
  });
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** One kind in a sentence ("hid 1 folio number"): the kind's name in lower case, PAN and Aadhaar as written. */
export function kindNoun(kind: HiddenKind): string {
  const name = KIND_NAME[kind] ?? kind;
  return KEEP_CASE.has(kind) ? name : name.charAt(0).toLowerCase() + name.slice(1);
}

export const HIDDEN_COPY = {
  label: "Hidden details",
  bar: "Personal details hidden",
  status: "Hidden from everyone but you",
  question: "Only show it if it isn't about a real customer. What is it?",
  keep: "Keep it hidden",
  show: "Show it",
  hide: "Hide it",
  note: "We note your reason with the idea.",
} as const;

/** C-HIDDEN.list/1 in the module's order, from the one source the review desk reads too (E-ENUMS show_reason). The
 * module's words keep its straight apostrophes, as the desk's "Shown, because it's an internal reference" does. */
export const SHOW_REASONS: { value: ShowReason; label: string }[] = (
  ["scheme_or_product_code", "internal_reference", "made_up_example"] as const
).map((value) => ({ value, label: SHOW_REASON_LABEL[value] }));

/** C-HIDDEN.list/3: "Shown, because it's a scheme or product code." */
export function shownLine(reason: ShowReason | undefined): string {
  const label = SHOW_REASONS.find((r) => r.value === reason)?.label;
  return label ? `Shown, because ${label}.` : "Shown";
}

export type Segment = { text: string; kind?: HiddenKind; at: number };

/** Where a part's source phrase sits in the person's text, for the underline (C-DRAFT-PANEL.behaviour/3), in the
 * text's own UTF-16 offsets. Case is ignored without changing the text: lower-casing first moves every offset after
 * a letter such as "İ", which lower-cases to two units. */
export function quoteRange(text: string, quote: string | null): { start: number; end: number } | null {
  if (!quote) return null;
  const exact = text.indexOf(quote);
  if (exact >= 0) return { start: exact, end: exact + quote.length };
  let m: RegExpExecArray | null;
  try {
    m = new RegExp(quote.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "iu").exec(text);
  } catch {
    return null;
  }
  return m ? { start: m.index, end: m.index + m[0].length } : null;
}

/** The person's text cut at each span, so the detail can be underlined without changing a character. Spans that
 * overlap, run past the end or are out of order are clipped; the text joined back is always the text given. */
export function segments(text: string, spans: HiddenSpan[] | undefined): Segment[] {
  const sorted = [...(spans ?? [])]
    .filter((s) => Number.isInteger(s.start) && Number.isInteger(s.end) && s.end > s.start)
    .sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let at = 0;
  for (const s of sorted) {
    const start = Math.max(s.start, at);
    const end = Math.min(s.end, text.length);
    if (start >= end) continue;
    if (start > at) out.push({ text: text.slice(at, start), at });
    out.push({ text: text.slice(start, end), kind: s.kind, at: start });
    at = end;
  }
  if (at < text.length || out.length === 0) out.push({ text: text.slice(at), at });
  return out;
}
