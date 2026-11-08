import type { Metadata } from "next";

export const metadata: Metadata = { title: "Share an idea" };

export default function Page() {
  return (
    <>
      <h1>Share an idea</h1>
      <p className="lead">
        Tell us about a problem you face, a fix you have thought of, or a new business idea. A missing answer
        never stops you sharing.
      </p>
      <p className="notice">The idea canvas opens here soon.</p>
    </>
  );
}
