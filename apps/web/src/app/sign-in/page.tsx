import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { SparkMark } from "@/components/spark-mark";
import { currentUser } from "@/server/auth/current";
import { allowedDomains } from "@/server/auth/codes";
import { draftLookup, type DraftCard } from "@/server/auth/drafts";
import { emailCodeOn } from "@/server/auth/email-code";
import {
  ATTEMPT_COOKIE,
  attemptKeyHash,
  cleanIntent,
  destination,
  draftFromPath,
  intentStore,
  isCheckStep,
  nextScreen,
  type Intent,
} from "@/server/auth/intents";
import { clockTime, isFailureRef, referenceLabel } from "@/server/auth/reference";
import {
  expiredSession,
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
  sessionTtlSeconds,
} from "@/server/auth/session";
import { itServiceDeskExtension, oidcConfig } from "@/server/config";

import { EmailCode } from "./email-code";
import { SsoForm } from "./sso-form";
import "./sign-in.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Sign in" };

type Params = Record<string, string | undefined>;

/** The S-02 state to show (L-AUTH.states). The email steps run in the browser once their switch is on. */
type State =
  | { kind: "email" }
  | { kind: "signing"; to: string }
  | { kind: "failed"; ref: string }
  | { kind: "refused"; ref: string }
  | { kind: "expired"; email: string; draft: DraftCard | null; intent: Intent };

const NEXT_LINES = {
  share: {
    title: "Next: Share a problem",
    line: "You land in the box with the cursor ready. Nothing to find again.",
    retry: "You will still go straight to Share a problem.",
  },
  home: {
    title: "Next: Your Home",
    line: "Your ideas, anything that needs you, and the box to share a problem.",
    retry: "You will still go to your Home.",
  },
} as const;

async function keptIntent(params: Params): Promise<Intent | null> {
  if (params.to || params.next) return cleanIntent({ to: params.to ?? params.next });
  const key = (await cookies()).get(ATTEMPT_COOKIE)?.value;
  if (!key || key.length > 128) return null;
  return intentStore()
    .find(attemptKeyHash(key), new Date())
    .catch(() => null);
}

async function stateFor(params: Params, intent: Intent | null): Promise<State> {
  if (isFailureRef(params.failed)) return { kind: "failed", ref: params.failed };
  if (isFailureRef(params.refused)) return { kind: "refused", ref: params.refused };
  if (params.signing === "1") return { kind: "signing", to: destination(intent ?? cleanIntent({ to: "/" })) };
  const open = intent?.draftId ? intent : params.next ? cleanIntent({ to: params.next }) : null;
  if (open?.draftId && draftFromPath(destination(open))) {
    const expired = await expiredSession((await cookies()).get(SESSION_COOKIE)?.value).catch(() => null);
    if (expired) {
      const draft = await draftLookup()
        .card(expired.userId, open.draftId)
        .catch(() => null);
      return { kind: "expired", email: expired.email, draft, intent: open };
    }
  }
  return { kind: "email" };
}

/** "Call the IT service desk on 4357" once IT gives the number; until then the line leaves it out. */
function deskOn(): string {
  const ext = itServiceDeskExtension();
  return ext ? `the IT service desk on ${ext}` : "the IT service desk";
}

/**
 * S-02 Sign in (L-AUTH). Shown only when silent single sign-on is not possible, fails, or a session expires; it
 * always says where the person lands next, and that nothing is lost (S-02.purpose). Single sign-on first; the
 * email code route shows only while `auth.email_code` is on (BLD-E002).
 */
export default async function SignIn({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  const me = await currentUser().catch(() => null);
  if (me) redirect(destination(cleanIntent({ to: params.to ?? params.next })));

  const intent = await keptIntent(params);
  const state = await stateFor(params, intent);
  const emailOn =
    state.kind === "failed" || state.kind === "email" || state.kind === "expired"
      ? await emailCodeOn()
      : false;
  const next = nextScreen(state.kind === "expired" ? state.intent : intent);
  const ssoIntent = state.kind === "expired" ? state.intent : params.to || params.next ? intent : null;
  const at = Number(params.at);

  return (
    <div className="si">
      <div className="si-amb" aria-hidden="true">
        <i className="a1" />
        <i className="a2" />
      </div>
      <div className="si-side">
        <header className="si-top">
          <Link href="/" className="si-brand">
            <SparkMark height={26} />
            1% Club
          </Link>
        </header>

        <main id="main" tabIndex={-1} className="si-main">
          <div className="si-card">
            {state.kind === "email" ? (
              emailOn ? (
                <EmailCode
                  initial="email"
                  desk={deskOn()}
                  domains={allowedDomains()}
                  intent={
                    ssoIntent ? { to: ssoIntent.to, draft_id: ssoIntent.draftId, step: ssoIntent.step } : null
                  }
                />
              ) : (
                <div className="si-step">
                  <h1 className="si-h1">Sign in to 1% Club</h1>
                  <SsoForm intent={ssoIntent} primary label="Use single sign-on" />
                </div>
              )
            ) : null}

            {state.kind === "signing" ? (
              <div className="si-step">
                {/* Continues at once to silent single sign-on (L-AUTH.rules/1); works with scripts off. */}
                <meta
                  httpEquiv="refresh"
                  content={`0;url=/auth/sso/start?silent=1&to=${encodeURIComponent(state.to)}`}
                />
                <h1 className="si-h1">Signing you in</h1>
                <p className="si-lead">
                  With your KFintech account, the same one you use for Outlook and Teams.
                </p>
                <div className="si-progress" aria-hidden="true">
                  <i />
                </div>
                {next ? (
                  <div className="si-next" role="status">
                    <span className="si-next-icon" aria-hidden="true">
                      +
                    </span>
                    <div>
                      <p className="si-next-title">{NEXT_LINES[next].title}</p>
                      <p className="si-next-line">{NEXT_LINES[next].line}</p>
                    </div>
                  </div>
                ) : null}
                <p className="si-small">
                  Usually under a second. Still here? <a href={state.to}>Continue</a>
                </p>
              </div>
            ) : null}

            {state.kind === "failed" ? (
              <div className="si-step">
                <h1 className="si-h1">We couldn&apos;t sign you in</h1>
                <div className="si-alert" role="alert">
                  <p className="si-alert-title">Your KFintech account didn&apos;t answer in time.</p>
                  <p>
                    This is usually a short network hiccup on the office Wi-Fi or VPN. Nothing you typed is
                    lost.
                  </p>
                </div>
                <a className="si-btn si-btn-primary" href="/auth/sso/start">
                  <LockIcon />
                  Try again
                </a>
                {next || emailOn ? (
                  <p className="si-small">
                    {next ? NEXT_LINES[next].retry : null}
                    {emailOn ? (
                      <>
                        {next ? " " : null}Or <a href="/sign-in">get a code by email instead</a>.
                      </>
                    ) : null}
                  </p>
                ) : null}
                <hr className="si-rule" />
                <p className="si-small">
                  Still stuck? Call {deskOn()} and give them this reference:{" "}
                  <strong className="si-ref">
                    {referenceLabel(state.ref, Number.isFinite(at) ? at : null)}
                  </strong>
                </p>
              </div>
            ) : null}

            {state.kind === "refused" ? (
              <div className="si-step">
                <h1 className="si-h1">We couldn&apos;t sign you in</h1>
                <div className="si-alert" role="alert">
                  <p className="si-alert-title">This account can&apos;t sign in to 1% Club.</p>
                  <p>
                    Call {deskOn()} and give them this reference:{" "}
                    <strong className="si-ref">
                      {referenceLabel(state.ref, Number.isFinite(at) ? at : null)}
                    </strong>
                  </p>
                </div>
              </div>
            ) : null}

            {state.kind === "expired" ? (
              <ExpiredState state={state} emailOn={emailOn} hours={await sessionHours()} />
            ) : null}
          </div>

          {oidcConfig().mode === "mock" && state.kind === "email" ? (
            <p className="si-dev">
              Development sign-in: type a synthetic employee ID such as <code>SYN-00002</code> as the username
              and leave the claims empty. <code>make seed</code> prints who each one is.
            </p>
          ) : null}
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

async function sessionHours(): Promise<number> {
  return Math.round(((await sessionTtlSeconds()) || SESSION_TTL_SECONDS) / 3600);
}

function ExpiredState({
  state,
  emailOn,
  hours,
}: {
  state: Extract<State, { kind: "expired" }>;
  emailOn: boolean;
  hours: number;
}) {
  const card = state.draft;
  const device = card?.savedOn ? ` on this ${card.savedOn}` : "";
  const intent = { to: state.intent.to, draft_id: state.intent.draftId, step: state.intent.step };
  return (
    <div className="si-step">
      <h1 className="si-h1">Sign in again to carry on</h1>
      <p className="si-lead">
        KFintech apps sign everyone out after {hours} hours. Your draft is safe, exactly as you left it.
      </p>
      {card ? (
        <div className="si-draft">
          <p className="si-draft-when">
            Draft, saved {clockTime(card.savedAt)}
            {device}
          </p>
          <p className="si-draft-title">{card.title}</p>
          {isCheckStep(card.step) || card.keptLine ? (
            <p className="si-draft-kept">
              {isCheckStep(card.step) ? "You were checking it." : null}
              {isCheckStep(card.step) && card.keptLine ? " " : null}
              {card.keptLine}
            </p>
          ) : null}
        </div>
      ) : null}
      {emailOn ? (
        <EmailCode
          initial="expired"
          desk={deskOn()}
          domains={allowedDomains()}
          email={state.email}
          intent={intent}
        />
      ) : (
        <SsoForm intent={state.intent} primary label="Use single sign-on" />
      )}
      <hr className="si-rule" />
      <p className="si-small">Trouble signing in? Call {deskOn()}.</p>
    </div>
  );
}

function LockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
      <rect x="3" y="7" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
