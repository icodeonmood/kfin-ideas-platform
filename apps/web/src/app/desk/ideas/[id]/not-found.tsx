import Link from "next/link";

import { NOT_FOUND_COPY } from "@/lib/desk/not-found";

/**
 * S-R2 when the worker gives no page (BLD-B277): an idea that is not there, or one this person may not open, such as
 * an admin without a review-desk role (J-COMMITTEE/4). It says the same in both cases, so it never tells anyone that
 * an idea exists (L-REVIEW, as L-CONVO/2 does for the conversation), in the 1% Club shell instead of Next's own
 * unbranded page. One heading, one line and the back link to Home that S-R3 uses (`.back` to `/`, BLD-B261).
 */
export default function ReviewerIdeaNotFound() {
  return (
    <>
      <p className="back-row">
        <Link className="back" href="/">
          {NOT_FOUND_COPY.home}
        </Link>
      </p>
      <section className="emp" aria-labelledby="nf-title">
        <h1 id="nf-title" className="emp-t">
          {NOT_FOUND_COPY.title}
        </h1>
        <p className="emp-b">{NOT_FOUND_COPY.body}</p>
      </section>
    </>
  );
}
