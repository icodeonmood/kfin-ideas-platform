/**
 * "Use single sign-on" (S-02, L-AUTH.rules/1): a form post to /auth/sso/start, so it works with scripts off and
 * meets the same-origin check. With an intent it starts a new attempt for that place; without one, the attempt the
 * browser already has keeps where the person was going (L-AUTH.rules/4).
 */
export type SsoIntent = { to?: string | null; draftId?: string | null; step?: string | null } | null;

export function SsoForm({
  intent,
  label,
  primary = false,
  id,
}: {
  intent: SsoIntent;
  label: string;
  primary?: boolean;
  id?: string;
}) {
  return (
    <form method="post" action="/auth/sso/start" id={id} className="si-sso">
      {intent?.to ? <input type="hidden" name="to" value={intent.to} /> : null}
      {intent?.draftId ? <input type="hidden" name="draft_id" value={intent.draftId} /> : null}
      {intent?.step ? <input type="hidden" name="step" value={intent.step} /> : null}
      <button type="submit" className={primary ? "si-btn si-btn-primary" : "si-btn si-btn-line"}>
        <KeyIcon />
        {label}
      </button>
    </form>
  );
}

function KeyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
      <circle cx="4.5" cy="11.5" r="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="m6.3 9.7 6.2-6.2M10.5 5.5l1.5 1.5M12 4l1 1"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
