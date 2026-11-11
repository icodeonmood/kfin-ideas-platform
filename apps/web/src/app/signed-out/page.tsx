import { SparkMark } from "@/components/spark-mark";

export default function SignedOut() {
  return (
    <section className="band stage entry" data-theme="zed" data-glow="1" aria-labelledby="entry-title">
      <div className="band-inner entry-inner">
        <div className="entry-copy">
          <h1 id="entry-title" className="t-display">
            You have signed out
          </h1>
          <p className="entry-action">
            <a className="btn btn-secondary btn-lg" href="/sign-in">
              Sign in again
            </a>
          </p>
        </div>
        <div className="entry-mark">
          <SparkMark height={300} className="entry-spark" />
          <p className="entry-tagline">1% spark. 99% sweat.</p>
        </div>
      </div>
    </section>
  );
}
