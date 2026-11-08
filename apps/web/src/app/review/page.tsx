import type { Metadata } from "next";

export const metadata: Metadata = { title: "Review" };

export default function Page() {
  return (
    <>
      <h1>Review</h1>
      <p className="lead">Ideas waiting for the review desk, soonest due first.</p>
      <p className="notice">The review queue opens here soon.</p>
    </>
  );
}
