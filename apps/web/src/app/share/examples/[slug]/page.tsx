import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { canvasConfig } from "@/server/canvas-config";

export const metadata: Metadata = { title: "What good looks like" };
export const dynamic = "force-dynamic";

/** One anonymised example per canvas section, from guidance/canvas/ in the company repo (§4.1). */
export default async function Example({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const example = (await canvasConfig()).examples.find((e) => e.slug === slug);
  if (!example) notFound();
  return (
    <article aria-labelledby="example-title">
      <p className="muted">What good looks like</p>
      <h1 id="example-title">{example.section}</h1>
      <h2>The question</h2>
      <p>{example.question}</p>
      <h2>A weak answer</h2>
      <blockquote>{example.weak}</blockquote>
      <h2>A strong answer</h2>
      <blockquote>{example.strong}</blockquote>
      <h2>Why it works</h2>
      <p>{example.why}</p>
    </article>
  );
}
