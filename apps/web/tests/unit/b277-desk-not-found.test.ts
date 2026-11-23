/**
 * BLD-B277, S-R2, J-COMMITTEE/4: when the worker gives no page (an idea that is not there, or an admin with no
 * review-desk role), S-R2 shows the 1% Club's own not-found page in the shell, never Next's unbranded one. It reads
 * the same in both cases, so it never says an idea exists. Synthetic data only.
 */
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));

const { default: ReviewerIdeaNotFound } = await import("@/app/desk/ideas/[id]/not-found");
const { NOT_FOUND_COPY } = await import("@/lib/desk/not-found");

describe("BLD-B277 S-R2 not-found", () => {
  const html = renderToStaticMarkup(createElement(ReviewerIdeaNotFound));

  it("has one heading, the line and S-R3's back link to Home", () => {
    expect(html.match(/<h1\b/g)).toHaveLength(1);
    expect(html).toContain(`<h1 id="nf-title" class="emp-t">${NOT_FOUND_COPY.title}</h1>`);
    expect(html).toContain(`<p class="emp-b">${NOT_FOUND_COPY.body}</p>`);
    const back = /<a ([^>]*)>([^<]*)<\/a>/.exec(html);
    expect(back?.[2]).toBe(NOT_FOUND_COPY.home);
    expect(back?.[1]).toContain('href="/"');
    expect(back?.[1]).toContain('class="back"');
  });

  it("is plain words: no code, no idea number, nothing that says an idea is there", () => {
    expect(NOT_FOUND_COPY.title).toBe("We couldn’t find that idea.");
    expect(html).not.toMatch(/404|IDEA-|not open to you|permission|review desk|could not be found/i);
  });
});
