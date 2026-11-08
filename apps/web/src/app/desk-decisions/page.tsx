import type { Metadata } from "next";

export const metadata: Metadata = { title: "Desk decisions" };

export default function Page() {
  return (
    <>
      <h1>Desk decisions</h1>
      <p className="lead">
        Everything the review desk has decided. You can reconsider a decision within 5 working days, with a
        reason.
      </p>
      <p className="notice">Desk decisions appear here once the review desk starts work.</p>
    </>
  );
}
