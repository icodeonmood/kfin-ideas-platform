import { oidcConfig } from "@/server/config";
import { safeNext } from "@/server/auth/session";

export const dynamic = "force-dynamic";

const ERRORS: Record<string, string> = {
  inactive:
    "Your account is not active in the HR directory. If you have just joined, please try again tomorrow.",
  no_email: "We couldn't read your work email from the sign-in service. Please contact the IT helpdesk.",
  idp_unavailable: "The sign-in service is not answering. Please try again in a minute.",
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
    <>
      <h1>Sign in</h1>
      {error ? (
        <p role="alert" className="notice notice-error">
          {error}
        </p>
      ) : null}
      <p className="lead">Use your KFintech account. There is no separate password for this site.</p>
      <p>
        <a className="button" href={`/auth/login?next=${encodeURIComponent(next)}`}>
          Sign in with your KFintech account
        </a>
      </p>
      {oidcConfig().mode === "mock" ? (
        <p className="dev-note">
          Development sign-in: type a synthetic employee ID such as <code>SYN-00002</code> as the username and
          leave the claims empty. <code>make seed</code> prints who each one is.
        </p>
      ) : null}
    </>
  );
}
