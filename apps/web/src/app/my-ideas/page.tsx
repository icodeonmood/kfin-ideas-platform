import type { Metadata } from "next";

export const metadata: Metadata = { title: "My ideas" };

export default function Page() {
  return (
    <>
      <h1>My ideas</h1>
      <p className="lead">Every idea you share is listed here with where it is now and what happens next.</p>
      <p className="notice">You haven&apos;t shared an idea yet.</p>
    </>
  );
}
