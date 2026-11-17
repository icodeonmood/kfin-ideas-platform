/**
 * L-HIDE offsets at the web edge (lane C, BLD-C068). The worker counts code points (Python's string offsets); the
 * browser counts UTF-16 code units (JavaScript's). They differ after any character outside the Basic Multilingual
 * Plane, such as an emoji, which takes two units and one code point.
 *
 * - Spans going out (`Hidden.spans`, `idea_messages.spans`): the web has the person's own text with them, so it
 *   converts with `spansToUtf16` before the underline is drawn.
 * - The desk's "Hide this" coming in: the web never holds the masked text the reviewer selected in, so it passes
 *   the browser's offsets on with `units: "utf16"` and the worker converts them against that text.
 */

export interface CodePointSpan {
  start: number;
  end: number;
  kind: string;
  hid?: string;
}

/** The UTF-16 offset for a code-point offset in `text`. */
export function codePointsToUtf16(text: string, offset: number): number {
  let units = 0;
  let points = 0;
  for (const ch of text) {
    if (points >= offset) break;
    units += ch.length;
    points += 1;
  }
  return units;
}

/** The code-point offset for a UTF-16 offset in `text`, or null when it is outside or splits a character. */
export function utf16ToCodePoints(text: string, offset: number): number | null {
  if (!Number.isInteger(offset) || offset < 0) return null;
  let units = 0;
  let points = 0;
  for (const ch of text) {
    if (units === offset) return points;
    units += ch.length;
    points += 1;
    if (units > offset) return null;
  }
  return units === offset ? points : null;
}

/** Spans from the worker (code points) as the browser counts them (UTF-16 units), for the dotted underline. */
export function spansToUtf16<T extends CodePointSpan>(text: string, spans: readonly T[]): T[] {
  return spans.map((s) => ({
    ...s,
    start: codePointsToUtf16(text, s.start),
    end: codePointsToUtf16(text, s.end),
  }));
}
