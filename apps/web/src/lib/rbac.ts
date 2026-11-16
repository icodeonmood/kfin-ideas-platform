/**
 * Roles and permissions (ARCHITECTURE §3.1), driven by policy/rbac.yaml (generated into rbac.json).
 * Pure functions: the proxy, route handlers, pages and tests all ask the same questions here.
 */
import policy from "./rbac.json";

export type Grant = { role: string; scope_id: string | null };

type Capabilities = Record<string, Record<string, string>>;
const capabilities = policy.capabilities as Capabilities;
const aliases = policy.role_aliases as Record<string, string>;

export const ROLE_COLUMNS: readonly string[] = policy.roles;

interface Route {
  method: string;
  template: string;
  pattern: RegExp;
  capabilities: string[];
}

function compile(line: string): Route {
  const [method, template, ...caps] = line.trim().split(/\s+/);
  if (!method || !template) throw new Error(`bad policy line: ${line}`);
  const body = template
    .split("/")
    .map((seg) => (/^\{[a-z_]+\}$/.test(seg) ? "[^/]+" : seg.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
    .join("/");
  return { method, template, pattern: new RegExp(`^${body}/?$`), capabilities: caps };
}

const endpoints = (policy.endpoints as string[]).map(compile);
const publicRoutes = (policy.public as string[]).map(compile);
const authExempt = (policy.auth_exempt as string[]).map(compile);
const beforePrivacy = (policy.before_privacy_notice as string[]).map(compile);
const pages = (policy.pages as string[]).map((line) => {
  const [path, ...caps] = line.trim().split(/\s+/);
  return { path: path!, capabilities: caps };
});

const normaliseMethod = (method: string) => (method.toUpperCase() === "HEAD" ? "GET" : method.toUpperCase());
const find = (routes: Route[], method: string, path: string) =>
  routes.find((r) => r.method === normaliseMethod(method) && r.pattern.test(path));

/** Everyone signed in is a contributor; aliases (core_chair → core_committee) add their target. */
export function effectiveRoles(grants: readonly Grant[]): Set<string> {
  const roles = new Set<string>(["contributor"]);
  for (const g of grants) {
    roles.add(g.role);
    const alias = aliases[g.role];
    if (alias) roles.add(alias);
  }
  return roles;
}

/** Scope values the roles hold for a capability ("yes", "own_lob", …). Empty means not allowed. */
export function scopesFor(roles: Set<string>, capability: string): string[] {
  const row = capabilities[capability];
  if (!row) throw new Error(`unknown capability ${capability}`);
  return Object.entries(row)
    .filter(([role]) => roles.has(role))
    .map(([, value]) => value);
}

export const can = (roles: Set<string>, capability: string) => scopesFor(roles, capability).length > 0;

export type Decision =
  | { kind: "public" }
  | { kind: "unknown" }
  | { kind: "allow"; capability: string; scopes: string[] }
  | { kind: "deny"; capability: string };

/** Endpoint-level decision. Row-level scopes are the handler's job. */
export function decide(roles: Set<string>, method: string, path: string): Decision {
  if (find(publicRoutes, method, path)) return { kind: "public" };
  const route = find(endpoints, method, path);
  if (!route) return { kind: "unknown" };
  for (const capability of route.capabilities) {
    const scopes = scopesFor(roles, capability);
    if (scopes.length) return { kind: "allow", capability, scopes };
  }
  return { kind: "deny", capability: route.capabilities.join("|") };
}

export const isPublic = (method: string, path: string) => Boolean(find(publicRoutes, method, path));
/** A sign-in route listed in `auth_exempt`: it runs without a session. Any other /auth path is refused (BLD-A177). */
export const isAuthExempt = (method: string, path: string) => Boolean(find(authExempt, method, path));
export const allowedBeforePrivacyNotice = (method: string, path: string) =>
  Boolean(find(beforePrivacy, method, path));

/** Capabilities a page needs (any of them), or undefined for pages open to everyone signed in. */
export function pageCapabilities(path: string): string[] | undefined {
  return pages.find((p) => path === p.path || path.startsWith(p.path + "/"))?.capabilities;
}

export function canSeePage(roles: Set<string>, path: string): boolean {
  const caps = pageCapabilities(path);
  return !caps || caps.some((c) => can(roles, c));
}

export type NavItem = { label: string; href: string };

type NavRule = { label: string; href: string; roles?: string[]; when_on?: string; when_off?: string };

/**
 * The menu for these roles. `switchesOn` names the kill switches that are on; an item tied to a switch shows only
 * while it is on (`when_on`) or off (`when_off`). Without it every switch counts as off (fail closed, §7.6).
 */
export function navFor(roles: Set<string>, switchesOn: ReadonlySet<string> = new Set()): NavItem[] {
  return (policy.navigation as NavRule[])
    .filter((item) => !item.roles || item.roles.some((r) => roles.has(r)))
    .filter((item) => !item.when_on || switchesOn.has(item.when_on))
    .filter((item) => !item.when_off || !switchesOn.has(item.when_off))
    .map(({ label, href }) => ({ label, href }));
}

/** §7.6 "Who can flip": `agent.*` covers every agent switch. */
export function canFlip(roles: Set<string>, switchName: string): boolean {
  const flippers = policy.kill_switch_flippers as Record<string, string[]>;
  // Own keys only: `in` would also match "constructor" or "__proto__" and then throw below (BLD-A171 review).
  const key = Object.hasOwn(flippers, switchName)
    ? switchName
    : switchName.startsWith("agent.")
      ? "agent.*"
      : undefined;
  return Boolean(key && flippers[key]!.some((r) => roles.has(r)));
}

/** Every sign-in route in the policy, for tests. */
export const AUTH_EXEMPT: ReadonlyArray<{ method: string; template: string }> = authExempt.map(
  ({ method, template }) => ({ method, template }),
);

/** Every endpoint in the policy, for tests and documentation. */
export const ENDPOINTS: ReadonlyArray<{ method: string; template: string; capabilities: string[] }> =
  endpoints.map(({ method, template, capabilities: caps }) => ({ method, template, capabilities: caps }));
