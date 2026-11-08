import type { Metadata } from "next";

export const metadata: Metadata = { title: "Wall" };

export default function Page() {
  return (
    <>
      <h1>Wall</h1>
      <p className="lead">Ideas from across KFintech, and what is already in the Garage.</p>
      <p className="notice">The wall fills up as colleagues share ideas.</p>
    </>
  );
}
