"use client";

import { useCallback, useState } from "react";

export type Grant = {
  id: string;
  role: string;
  scope_id: string | null;
  name: string;
  email: string;
  lob_id: string | null;
};

const ROLES: Array<{ value: string; label: string; scope?: string }> = [
  { value: "reviewer", label: "Review desk" },
  { value: "committee", label: "Ones Committee" },
  { value: "display", label: "Office and launch screens" },
  { value: "admin", label: "Admin" },
  { value: "infosec", label: "InfoSec (kill switches)" },
  { value: "hr", label: "HR (wall switch)" },
];
// Grants made before the 1% Club's roles (DEC-102) are still listed, by these names, until someone removes them.
const RETIRED: Record<string, string> = {
  core_committee: "Core committee member (retired role)",
  core_chair: "Core committee chair (retired role)",
  lob_committee: "LOB committee member (retired role)",
  appeal_panel: "Appeal panel (retired role)",
  working_group: "Working group member (retired role)",
  sponsor: "Sponsor (retired role)",
  ceo: "CEO (retired role)",
  build_team: "Build team",
};
const LABEL: Record<string, string> = {
  ...RETIRED,
  ...Object.fromEntries(ROLES.map((r) => [r.value, r.label])),
};
const ERRORS: Record<string, string> = {
  no_such_person: "No active person has that email address.",
  already_granted: "That person already has this role.",
  scope_required: "This role needs a scope in the format shown.",
  scope_not_allowed: "This role does not take a scope. Leave it empty.",
  unknown_role: "That role can't be given any more.",
  reason_required: "Please give a reason of at least 10 characters.",
  last_admin: "You can't remove the last admin.",
};

export function Roles({ initial }: { initial: Grant[] }) {
  const [grants, setGrants] = useState<Grant[]>(initial);
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    const res = await fetch("/api/admin/roles", { cache: "no-store" });
    if (res.ok) setGrants(((await res.json()) as { grants: Grant[] }).grants);
  }, []);

  return (
    <section aria-labelledby="roles-title">
      <h2 id="roles-title">Roles</h2>
      <p role="status" aria-live="polite" className="sr-status">
        {message}
      </p>
      <GrantForm
        onDone={async (text) => {
          setMessage(text);
          await load();
        }}
      />
      {
        <table className="table">
          <caption className="visually-hidden">People with roles</caption>
          <thead>
            <tr>
              <th scope="col">Person</th>
              <th scope="col">Role</th>
              <th scope="col">Scope</th>
              <th scope="col">Remove</th>
            </tr>
          </thead>
          <tbody>
            {grants.map((g) => (
              <tr key={g.id}>
                <th scope="row">
                  {g.name}
                  <div className="muted">{g.email}</div>
                </th>
                <td>{LABEL[g.role] ?? g.role}</td>
                <td>{g.scope_id ?? "—"}</td>
                <td>
                  <Revoke
                    grant={g}
                    onDone={async (text) => {
                      setMessage(text);
                      await load();
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    </section>
  );
}

function GrantForm({ onDone }: { onDone: (message: string) => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("reviewer");
  const [scope, setScope] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const needsScope = ROLES.find((r) => r.value === role)?.scope;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const res = await fetch("/api/admin/roles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role, scope: needsScope ? scope : null, reason }),
    });
    if (!res.ok) {
      const code = ((await res.json().catch(() => ({}))) as { error?: string }).error ?? "";
      setError(ERRORS[code] ?? "That didn't work. Please check the details and try again.");
      return;
    }
    setError("");
    setEmail("");
    setScope("");
    setReason("");
    await onDone(`${LABEL[role]} role given.`);
  }

  return (
    <form onSubmit={submit} noValidate className="stack-form" aria-labelledby="grant-title">
      <h3 id="grant-title">Give someone a role</h3>
      {error ? (
        <p id="grant-error" role="alert" className="field-error">
          {error}
        </p>
      ) : null}
      <label htmlFor="grant-email">Work email</label>
      <input
        id="grant-email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        autoComplete="off"
      />
      <label htmlFor="grant-role">Role</label>
      <select id="grant-role" value={role} onChange={(e) => setRole(e.target.value)}>
        {ROLES.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      {needsScope ? (
        <>
          <label htmlFor="grant-scope">Scope</label>
          <p id="grant-scope-hint" className="hint">
            {needsScope}
          </p>
          <input
            id="grant-scope"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            aria-describedby="grant-scope-hint"
            required
          />
        </>
      ) : null}
      <label htmlFor="grant-reason">Reason</label>
      <textarea
        id="grant-reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={2}
        required
      />
      <div className="actions">
        <button type="submit" className="button">
          Give role
        </button>
      </div>
    </form>
  );
}

function Revoke({ grant, onDone }: { grant: Grant; onDone: (message: string) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const label = `Remove ${LABEL[grant.role] ?? grant.role} from ${grant.name}`;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const res = await fetch(`/api/admin/roles/${grant.id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) {
      const code = ((await res.json().catch(() => ({}))) as { error?: string }).error ?? "";
      setError(ERRORS[code] ?? "That didn't work.");
      return;
    }
    setOpen(false);
    await onDone(`Removed. ${grant.name} no longer has this role.`);
  }

  if (!open) {
    return (
      <button
        type="button"
        className="button button-secondary"
        onClick={() => setOpen(true)}
        aria-label={label}
      >
        Remove…
      </button>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="inline-form">
      <label htmlFor={`revoke-${grant.id}`}>Reason for removing</label>
      <textarea
        id={`revoke-${grant.id}`}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={2}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `revoke-${grant.id}-error` : undefined}
      />
      {error ? (
        <p id={`revoke-${grant.id}-error`} className="field-error">
          {error}
        </p>
      ) : null}
      <div className="actions">
        <button type="submit" className="button">
          Remove role
        </button>
        <button type="button" className="button button-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
