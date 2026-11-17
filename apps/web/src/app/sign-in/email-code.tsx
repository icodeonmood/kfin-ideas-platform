"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

import { SsoForm } from "./sso-form";

/**
 * S-02's email route (L-AUTH.rules/2-3, V-FIELDS.signin, S-02.rules/1-3): work email → a 6-digit code → signed in.
 * Rendered only while `auth.email_code` is on (BLD-E002). Every count and time comes from the server's answers.
 *
 * - "Send code" stays disabled until the address is a work address (V-FIELDS.signin/1-2).
 * - The code is one input (paste, one-time-code autofill, numeric keypad) drawn as six boxes (C-FIELD.kinds);
 *   "Sign in" waits for six digits, and the sixth digit submits.
 * - The resend countdown is a timer that is not read out every second (S-02.rules/3).
 * - Steps slide forward and back; focus goes to the first field of each step (S-02.rules/1).
 */
type Intent = { to: string; draft_id: string | null; step: string | null } | null;
type Step = "email" | "code" | "going";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const isWork = (email: string, domains: string[]) => {
  const e = email.trim().toLowerCase();
  return EMAIL.test(e) && domains.includes(e.split("@").pop() ?? "");
};
const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

const MESSAGES = {
  not_work_email: "Use your KFintech email, like name@kfintech.com.",
  rate_limited: "Too many tries. Wait 10 minutes, or use single sign-on.",
  code_expired: "That code has run out. We've sent a new one.",
  unavailable: "Something went wrong on our side. Please try again in a minute.",
} as const;

async function post(path: string, body: unknown): Promise<{ status: number; data: Record<string, unknown> }> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return {
    status: res.status,
    data: ((await res.json().catch(() => ({}))) ?? {}) as Record<string, unknown>,
  };
}

export function EmailCode({
  initial,
  domains,
  email: knownEmail,
  intent,
  desk,
}: {
  initial: "email" | "expired";
  domains: string[];
  email?: string;
  intent: Intent;
  /** "the IT service desk on 4357", or without the number until IT gives it. */
  desk: string;
}) {
  const ids = useId();
  const [step, setStep] = useState<Step>("email");
  const [dir, setDir] = useState<"fwd" | "back">("fwd");
  const [email, setEmail] = useState(knownEmail ?? "");
  const [touched, setTouched] = useState(false);
  const [sentTo, setSentTo] = useState("");
  const [validMinutes, setValidMinutes] = useState(10);
  const [code, setCode] = useState("");
  const [wrong, setWrong] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [left, setLeft] = useState(0);
  const [busy, setBusy] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  const codeRef = useRef<HTMLInputElement>(null);
  const first = useRef(true);

  const work = isWork(email, domains);
  const ssoId = `${ids}-sso`;
  // L-AUTH.errors: the account line names the desk the way the server page does.
  const message = useCallback(
    (error: unknown): string =>
      error === "account_disabled"
        ? `This account can't sign in to 1% Club. Call ${desk}.`
        : (MESSAGES[String(error) as keyof typeof MESSAGES] ?? MESSAGES.unavailable),
    [desk],
  );

  useEffect(() => {
    if (left <= 0) return;
    const t = setTimeout(() => setLeft((n) => Math.max(0, n - 1)), 1000);
    return () => clearTimeout(t);
  }, [left]);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    (step === "code" ? codeRef : emailRef).current?.focus();
  }, [step]);

  const send = useCallback(
    async (address: string) => {
      setBusy(true);
      setNotice(null);
      try {
        const { status, data } = await post("/auth/code/send", { email: address, intent });
        if (status === 200) {
          setSentTo(String(data.sent_to ?? address));
          setValidMinutes(Number(data.valid_minutes ?? 10));
          setLeft(Number(data.resend_in_seconds ?? 45));
          setCode("");
          setWrong(null);
          setDir("fwd");
          setStep("code");
          return;
        }
        if (data.error === "too_soon") {
          setLeft(Number(data.resend_in_seconds ?? 45));
          setSentTo(address);
          setDir("fwd");
          setStep("code");
          return;
        }
        setNotice(message(data.error));
      } catch {
        setNotice(MESSAGES.unavailable);
      } finally {
        setBusy(false);
      }
    },
    [intent, message],
  );

  const verify = useCallback(
    async (value: string) => {
      if (value.length !== 6 || busy) return;
      setBusy(true);
      setNotice(null);
      try {
        const { status, data } = await post("/auth/code/verify", { email: sentTo, code: value });
        if (status === 200 && typeof data.to === "string") {
          setStep("going");
          window.location.assign(data.to);
          return;
        }
        if (data.error === "wrong_code") {
          setWrong(Number(data.tries_left ?? 0));
          return;
        }
        if (data.error === "code_expired") {
          setCode("");
          setWrong(null);
          setLeft(45);
        }
        setNotice(message(data.error));
      } catch {
        setNotice(MESSAGES.unavailable);
      } finally {
        setBusy(false);
      }
    },
    [busy, sentTo, message],
  );

  const hidden = (
    <SsoForm
      id={ssoId}
      intent={intent ? { to: intent.to, draftId: intent.draft_id, step: intent.step } : null}
      label="Use single sign-on"
    />
  );

  if (step === "going") {
    // The code is accepted and the browser is on its way; only the board's words (S-02.states Signing you in).
    return (
      <div className="si-step" data-dir="fwd" role="status">
        <h1 className="si-h1">Signing you in</h1>
      </div>
    );
  }

  if (step === "code") {
    const tries = wrong === null ? null : `${wrong} ${wrong === 1 ? "try" : "tries"} left.`;
    return (
      <div className="si-step" data-dir={dir} key="code">
        <div hidden>{hidden}</div>
        <h1 className="si-h1">Check your email</h1>
        <p className="si-lead">
          We sent a 6-digit code to {sentTo}. It works for {validMinutes} minutes.{" "}
          <button
            type="button"
            className="si-link"
            onClick={() => {
              setDir("back");
              setStep("email");
              setNotice(null);
            }}
          >
            Change email
          </button>
        </p>
        <form
          className="si-code-form"
          onSubmit={(e) => {
            e.preventDefault();
            void verify(code);
          }}
        >
          <div className={wrong !== null ? "si-otp si-otp-bad" : "si-otp"}>
            <input
              ref={codeRef}
              id={`${ids}-code`}
              className="si-otp-input"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]*"
              maxLength={6}
              aria-label="6-digit code"
              aria-invalid={wrong !== null}
              aria-describedby={wrong !== null ? `${ids}-wrong` : undefined}
              value={code}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, "").slice(0, 6);
                setCode(v);
                setWrong(null);
                if (v.length === 6) void verify(v);
              }}
            />
            <div className="si-otp-boxes" aria-hidden="true">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <span key={i} className={code[i] ? "on" : i === code.length ? "cur" : undefined}>
                  {code[i] ?? ""}
                </span>
              ))}
            </div>
          </div>
          {wrong !== null ? (
            <p id={`${ids}-wrong`} className="si-error" role="alert">
              That code didn’t match. Check the latest email from 1% Club. {tries}
            </p>
          ) : null}
          {notice ? (
            <p className="si-error" role="alert">
              {notice}
            </p>
          ) : null}
          {left > 0 ? (
            <p className="si-small" role="timer" aria-live="off">
              You can ask for a new code in {clock(left)}.
            </p>
          ) : (
            <p className="si-small">
              <button type="button" className="si-link" disabled={busy} onClick={() => void send(sentTo)}>
                Send a new code
              </button>
            </p>
          )}
          <button type="submit" className="si-btn si-btn-primary" disabled={code.length !== 6 || busy}>
            Sign in
          </button>
        </form>
        <p className="si-small">
          Not in your inbox? Check Junk, or{" "}
          <button type="submit" form={ssoId} className="si-link">
            use single sign-on
          </button>
          .
        </p>
      </div>
    );
  }

  if (initial === "expired" && knownEmail) {
    return (
      <div className="si-step" data-dir={dir} key="expired">
        <div hidden>{hidden}</div>
        {notice ? (
          <p className="si-error" role="alert">
            {notice}
          </p>
        ) : null}
        <div className="si-dock">
          <button
            type="button"
            className="si-btn si-btn-primary"
            disabled={busy}
            onClick={() => void send(knownEmail)}
          >
            <span className="si-desk">Send a code to {knownEmail}</span>
            <span className="si-phone">
              <LockIcon />
              Send a code and carry on
            </span>
          </button>
          <p className="si-center">
            <button type="submit" form={ssoId} className="si-link">
              Use single sign-on instead
            </button>
          </p>
        </div>
      </div>
    );
  }

  const fieldError = touched && email.trim() !== "" && !work;
  // Phone (PhoneSignIn): single sign-on in the middle, the title and work email in one bottom sheet, no help line.
  return (
    <div className="si-step si-step-email" data-dir={dir} key="email">
      <div className="si-phone">
        <div className="si-sso-mid">
          <SsoForm
            intent={intent ? { to: intent.to, draftId: intent.draft_id, step: intent.step } : null}
            label="Use single sign-on"
          />
        </div>
      </div>
      <div className="si-sheet">
        <h1 className="si-h1">Sign in to 1% Club</h1>
        <form
          className="si-email-form"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            setTouched(true);
            if (work) void send(email.trim().toLowerCase());
          }}
        >
          <label htmlFor={`${ids}-email`} className="si-label">
            <span className="si-desk">Work email</span>
            <span className="si-phone">Use your work email</span>
          </label>
          <input
            ref={emailRef}
            id={`${ids}-email`}
            className="si-input"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="name@kfintech.com"
            value={email}
            aria-invalid={fieldError}
            aria-describedby={`${ids}-email-help`}
            onChange={(e) => setEmail(e.target.value)}
            onBlur={() => setTouched(true)}
          />
          <p id={`${ids}-email-help`} className={fieldError ? "si-help si-help-bad" : "si-help"}>
            {fieldError ? (
              MESSAGES.not_work_email
            ) : (
              <span className="si-desk">Use your official KFintech email ID to sign in.</span>
            )}
          </p>
          {notice ? (
            <p className="si-error" role="alert">
              {notice}
            </p>
          ) : null}
          <button type="submit" className="si-btn si-btn-primary" disabled={!work || busy}>
            Send code
          </button>
        </form>
        <div className="si-desk">
          <p className="si-or">
            <span>or</span>
          </p>
          <SsoForm
            id={ssoId}
            intent={intent ? { to: intent.to, draftId: intent.draft_id, step: intent.step } : null}
            label="Use single sign-on"
          />
        </div>
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
