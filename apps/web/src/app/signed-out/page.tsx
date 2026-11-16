import Link from "next/link";
import { redirect } from "next/navigation";

import { SparkMark } from "@/components/spark-mark";
import { currentUser } from "@/server/auth/current";

import "../sign-in/sign-in.css";

export const dynamic = "force-dynamic";

/** After "Sign out": signed out, so no shell; the same frame as S-02 (its own top row, main and footer). */
export default async function SignedOut() {
  const me = await currentUser().catch(() => null);
  if (me) redirect("/");
  return (
    <div className="si">
      <div className="si-side">
        <header className="si-top">
          <Link href="/" className="si-brand">
            <SparkMark height={26} />
            1% Club
          </Link>
        </header>
        <main id="main" tabIndex={-1} className="si-main">
          <div className="si-card">
            <div className="si-step">
              <h1 className="si-h1">You have signed out</h1>
              <a className="si-btn si-btn-primary" href="/sign-in">
                Sign in again
              </a>
            </div>
          </div>
        </main>
        <footer className="si-foot">
          <p>1% Club, a KFintech programme</p>
        </footer>
      </div>
      <aside className="si-lit" aria-labelledby="si-tagline">
        <SparkMark height={260} className="si-lit-mark" />
        <p id="si-tagline" className="si-tagline">
          1% spark. 99% sweat.
        </p>
      </aside>
    </div>
  );
}
