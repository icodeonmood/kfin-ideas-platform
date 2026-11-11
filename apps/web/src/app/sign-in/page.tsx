import { SparkMark } from "@/components/spark-mark";
import { Status } from "@/components/status";
import { oidcConfig } from "@/server/config";
import { safeNext } from "@/server/auth/session";

export const dynamic = "force-dynamic";

const ERRORS: Record<string, string> = {
  inactive:
    "Your account is not active in the HR directory. If you have just joined, please try again tomorrow.",
  no_email: "We couldn't read your work email from the sign-in service. Please contact the IT helpdesk.",
  idp_unavailable: "The sign-in service is not answering. Please try again in a minute.",
  identity_mismatch: "Your account details don't match the HR directory. Please contact the IT helpdesk.",
  email_not_kfin: "Please sign in with your KFintech work account.",
};
const DEFAULT_ERROR = "Signing in didn't work. Please try again.";

export default async function SignIn({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const next = safeNext(params.next);
  const error = params.error ? (ERRORS[params.error] ?? DEFAULT_ERROR) : null;
  return (
    <section className="band stage entry" data-theme="zed" data-glow="1" aria-labelledby="entry-title">
      <div className="band-inner entry-inner">
        <div className="entry-copy">
          <h1 id="entry-title" className="t-display">
            Sign in
          </h1>
          {error ? <Status kind="error" title={error} /> : null}
          <p className="lead entry-lead">
            Use your KFintech account to open 1% Club. There is no separate password.
          </p>
          <p className="entry-action">
            <a className="btn btn-primary btn-lg" href={`/auth/login?next=${encodeURIComponent(next)}`}>
              Sign in with your KFintech account
            </a>
          </p>
          {oidcConfig().mode === "mock" ? (
            <p className="dev-note entry-dev">
              Development sign-in: type a synthetic employee ID such as <code>SYN-00002</code> as the username
              and leave the claims empty. <code>make seed</code> prints who each one is.
            </p>
          ) : null}
        </div>
        <div className="entry-mark">
          <SparkMark height={300} className="entry-spark" />
          <p className="entry-tagline">1% spark. 99% sweat.</p>
        </div>
      </div>
    </section>
  );
}
