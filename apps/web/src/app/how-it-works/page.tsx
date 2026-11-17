import type { Metadata } from "next";
import Link from "next/link";

import { stages } from "@/lib/how-it-works";
import { promises } from "@/server/promises";

import "./how.css";

export const metadata: Metadata = { title: "What happens after you share" };
export const dynamic = "force-dynamic";

/**
 * S-H4 "What happens after you share": the five stages as a track that draws itself on arrival (S-H4/4; still with
 * reduced motion), and one button at the end, "Share your first problem" (S-H4/2).
 */
export default async function Page() {
  const config = await promises();
  return (
    <div className="hw">
      <Link href="/" className="hw-back">
        <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
          <path d="M10 3.5 5.5 8l4.5 4.5" />
        </svg>
        Home
      </Link>
      <h1 className="hw-title">What happens after you share</h1>
      <ol className="hw-steps">
        {stages(config.review.decide_by_working_days).map((s, k) => (
          <li key={s.title} className="hw-step" style={{ animationDelay: `${k * 120}ms` }}>
            <span className="hw-dot" aria-hidden="true">
              {k + 1}
            </span>
            <div>
              <h2 className="hw-h">{s.title}</h2>
              <p className="hw-body">{s.body}</p>
            </div>
            <p className="hw-when">{s.when}</p>
          </li>
        ))}
      </ol>
      <div className="hw-acts">
        <Link href="/share" className="hw-btn">
          Share your first problem
        </Link>
      </div>
    </div>
  );
}
