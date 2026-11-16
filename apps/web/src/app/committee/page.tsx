import type { Metadata } from "next";

export const metadata: Metadata = { title: "Committee" };

/**
 * Holding page. Scoring rounds, cycles, presentations and the links to desk decisions, appeals and reports are
 * retired (DEC-106, R1, R8 to R10, R14); lane B rebuilds this route as the Ones Committee window (S-R4).
 */
export default function Committee() {
  return (
    <>
      <h1>Committee</h1>
      <p className="lead">
        The review desk&apos;s decisions will show here, each with the time the committee has to extend or
        reverse it.
      </p>
    </>
  );
}
