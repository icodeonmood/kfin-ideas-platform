import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { SparkMark } from "@/components/spark-mark";
import { currentUser } from "@/server/auth/current";
import { allowedDomains } from "@/server/auth/codes";
import { draftLookup, savedOnWords, type DraftCard } from "@/server/auth/drafts";
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
  retryHref,
  signInHref,
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
import { askingDevice } from "@/server/shell";

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

/** The `cameFrom` tweak's words (reference/prototype SignIn and PhoneSignIn: nextTitle, nextLine, retryNote). */
const NEXT_LINES = {
  share: {
    name: "Share a problem",
    line: "You land in the box with the cursor ready. Nothing to find again.",
    retry: "You will still go straight to Share a problem.",
  },
  home: {
    name: "Your Home",
    line: "Your ideas, anything that needs you, and the box to share a problem.",
    retry: "You will still go to your Home.",
  },
} as const;

/**
 * The place this page keeps (L-AUTH.rules/4): the link's `to` (or the proxy's `next`), else the browser's kept row.
 * When both name the same place, the row wins: it also knows which part of Check it the draft was at.
 */
async function keptIntent(params: Params): Promise<Intent | null> {
  const asked = params.to || params.next ? cleanIntent({ to: params.to ?? params.next }) : null;
  const key = (await cookies()).get(ATTEMPT_COOKIE)?.value;
  const row =
    key && key.length <= 128
      ? await intentStore()
          .find(attemptKeyHash(key), new Date())
          .catch(() => null)
      : null;
  if (!asked) return row;
  return row && destination(row) === destination(asked) ? row : asked;
}

async function stateFor(params: Params, intent: Intent | null): Promise<State> {
  if (isFailureRef(params.failed)) return { kind: "failed", ref: params.failed };
  if (isFailureRef(params.refused)) return { kind: "refused", ref: params.refused };
  if (params.signing === "1") return { kind: "signing", to: destination(intent ?? cleanIntent({ to: "/" })) };
  const open = intent?.draftId ? intent : params.next ? cleanIntent({ to: params.next }) : null;
  if (open?.draftId && draftFromPath(destination(open))) {
    const expired = await expiredSession((await cookies()).get(SESSION_COOKIE)?.value).catch(() => null);
    if (expired) {
      const asking = await askingDevice();
      const draft = await draftLookup()
        .card(expired.userId, open.draftId, asking.id)
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
 *
 * Copy is verbatim from reference/copy/SignIn.md (desktop) and PhoneSignIn.md (phone, 640 px and below), apostrophes
 * included. Where the two boards' words differ, both are in the page and the width shows one: `si-desk` / `si-phone`
 * wrappers, and display:none hides the other from screen readers too (BLD-A179).
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
  const ref =
    state.kind === "failed" || state.kind === "refused"
      ? referenceLabel(state.ref, Number.isFinite(at) ? at : null)
      : "";

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
                  <>
                    <div className="si-desk">
                      <div className="si-next" role="status">
                        <span className="si-next-icon" aria-hidden="true">
                          +
                        </span>
                        <div>
                          <p className="si-next-title">Next: {NEXT_LINES[next].name}</p>
                          <p className="si-next-line">{NEXT_LINES[next].line}</p>
                        </div>
                      </div>
                    </div>
                    <div className="si-phone">
                      <p className="si-next si-next-one" role="status">
                        <span className="si-next-icon" aria-hidden="true">
                          +
                        </span>
                        <span>
                          Next: <b>{NEXT_LINES[next].name}</b>. {NEXT_LINES[next].line}
                        </span>
                      </p>
                    </div>
                  </>
                ) : null}
                <div className="si-desk">
                  <p className="si-small">
                    Usually under a second. Still here? <a href={state.to}>Continue</a>
                  </p>
                </div>
                <div className="si-phone">
                  <p className="si-center si-dock">
                    <a href={state.to}>Still here? Continue</a>
                  </p>
                </div>
              </div>
            ) : null}

            {state.kind === "failed" ? (
              <div className="si-step">
                <div className="si-desk">
                  <h1 className="si-h1">We couldn&apos;t sign you in</h1>
                </div>
                <div className="si-phone">
                  <h1 className="si-h1">We couldn’t sign you in</h1>
                </div>
                <div className="si-alert" role="alert">
                  <p className="si-alert-title">Your KFintech account didn&apos;t answer in time.</p>
                  <div className="si-desk">
                    <p>
                      This is usually a short network hiccup on the office Wi-Fi or VPN. Nothing you typed is
                      lost.
                    </p>
                  </div>
                  <div className="si-phone">
                    <p>Usually a short network hiccup. Nothing you typed is lost.</p>
                  </div>
                </div>
                <div className="si-desk">
                  <a className="si-btn si-btn-primary" href={retryHref(ssoIntent)}>
                    <LockIcon />
                    Try again
                  </a>
                  {next || emailOn ? (
                    <p className="si-small">
                      {next ? NEXT_LINES[next].retry : null}
                      {emailOn ? (
                        <>
                          {next ? " " : null}Or{" "}
                          <a href={signInHref(ssoIntent)}>get a code by email instead</a>.
                        </>
                      ) : null}
                    </p>
                  ) : null}
                  <hr className="si-rule" />
                  <p className="si-small">
                    Still stuck? Call {deskOn()} and give them this reference:{" "}
                    <strong className="si-ref">{ref}</strong>
                  </p>
                </div>
                <div className="si-phone">
                  <p className="si-small">
                    Still stuck? Call {deskOn()} with reference <strong className="si-ref">{ref}</strong>.
                  </p>
                  <div className="si-dock">
                    <a className="si-btn si-btn-primary" href={retryHref(ssoIntent)}>
                      <LockIcon />
                      Try again
                    </a>
                    {emailOn ? (
                      <p className="si-center">
                        <a href={signInHref(ssoIntent)}>Get a code by email instead</a>
                      </p>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : null}

            {state.kind === "refused" ? (
              <div className="si-step">
                <h1 className="si-h1">We couldn&apos;t sign you in</h1>
                <div className="si-alert" role="alert">
                  <p className="si-alert-title">This account can&apos;t sign in to 1% Club.</p>
                  <p>
                    Call {deskOn()} and give them this reference: <strong className="si-ref">{ref}</strong>
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
  // "on this laptop" when this browser saved it (the board's line), "on your phone" when another device did (BLD-A227)
  const device = savedOnWords(card?.savedOn ?? null);
  const intent = { to: state.intent.to, draft_id: state.intent.draftId, step: state.intent.step };
  return (
    <div className="si-step">
      <h1 className="si-h1">Sign in again to carry on</h1>
      <div className="si-desk">
        <p className="si-lead">
          KFintech apps sign everyone out after {hours} hours. Your draft is safe, exactly as you left it.
        </p>
      </div>
      <div className="si-phone">
        <p className="si-lead">KFintech apps sign everyone out after {hours} hours. Your draft is safe.</p>
      </div>
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
      <div className="si-desk">
        <hr className="si-rule" />
        <p className="si-small">Trouble signing in? Call {deskOn()}.</p>
      </div>
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
