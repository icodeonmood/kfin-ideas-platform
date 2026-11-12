import { NextResponse, type NextRequest } from "next/server";

import { BANNERS, switchesFor } from "@/lib/killswitch-routes";
import { allowedBeforePrivacyNotice, canSeePage, decide, effectiveRoles, isPublic } from "@/lib/rbac";
import {
  cookieOptions,
  readSession,
  refreshSession,
  SESSION_COOKIE,
  type SessionInfo,
} from "@/server/auth/session";
import { appBaseUrl } from "@/server/config";
import { isOn, switchStates } from "@/server/killswitch";
import { log } from "@/server/log";

const PUBLIC_PAGES = new Set(["/sign-in", "/signed-out"]);
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

const json = (status: number, body: Record<string, unknown>, headers: Record<string, string> = {}) =>
  NextResponse.json(body, { status, headers: { "Cache-Control": "no-store", ...headers } });
const redirect = (path: string) => NextResponse.redirect(new URL(path, appBaseUrl()));

/**
 * Runs before every request except static files (Next.js proxy, Node.js runtime). In order:
 * cross-origin writes refused → session (401 / sign-in) → privacy notice (403 / notice page) → RBAC from
 * policy/rbac.yaml (unknown 404, denied 403) → kill switches (503 with a banner, §7.6) → sliding session refresh.
 */
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const method = request.method.toUpperCase();
  if (pathname.includes("//")) return json(400, { error: "bad_path" }); // no "//api/…" lookalikes
  const isApi = pathname.startsWith("/api/");

  // CSRF defence on top of SameSite=Lax: a browser always sends Origin on a cross-site write.
  const origin = request.headers.get("origin");
  if (!SAFE_METHODS.has(method) && origin && origin !== appBaseUrl().origin) {
    return json(403, { error: "cross_origin" });
  }
  if (pathname.startsWith("/auth/") || PUBLIC_PAGES.has(pathname) || (isApi && isPublic(method, pathname))) {
    return NextResponse.next();
  }

  const token = request.cookies.get(SESSION_COOKIE)?.value;
  let session: SessionInfo | null;
  try {
    session = await readSession(token);
  } catch {
    log.error("auth.session_read_failed");
    return json(503, {
      error: "unavailable",
      banner: "Something went wrong on our side. Please try again in a minute.",
    });
  }
  if (!session) {
    return isApi
      ? json(401, { error: "sign_in_required" })
      : redirect(`/sign-in?next=${encodeURIComponent(pathname + search)}`);
  }

  let response: NextResponse | undefined;
  if (!session.privacyAccepted) {
    if (isApi && !allowedBeforePrivacyNotice(method, pathname)) {
      response = json(403, { error: "privacy_notice_required" });
    } else if (!isApi && pathname !== "/privacy-notice") {
      response = redirect(`/privacy-notice?next=${encodeURIComponent(pathname + search)}`);
    }
  }

  const roles = effectiveRoles(session.grants);
  if (!response && isApi) {
    const decision = decide(roles, method, pathname);
    if (decision.kind === "unknown") response = json(404, { error: "not_found" });
    else if (decision.kind === "deny") response = json(403, { error: "forbidden" });
    else response = await killSwitchCheck(method, pathname);
  } else if (!response && !canSeePage(roles, pathname)) {
    response = redirect("/");
  }

  response ??= NextResponse.next();
  if (session.needsRefresh && token) {
    await refreshSession(token);
    response.cookies.set(SESSION_COOKIE, token, cookieOptions());
  }
  return response;
}

async function killSwitchCheck(method: string, pathname: string): Promise<NextResponse | undefined> {
  const needed = switchesFor(method, pathname);
  if (needed.length === 0) return undefined;
  let states;
  try {
    states = await switchStates();
  } catch {
    // Cannot read the switches: refuse the change rather than risk running a killed feature.
    log.error("killswitch.read_failed", { method });
    return json(503, {
      error: "unavailable",
      banner: "Something went wrong on our side. Please try again in a minute.",
    });
  }
  const off = needed.find((name) => !isOn(states, name));
  return off
    ? json(503, { error: "paused", switch: off, banner: BANNERS[off] }, { "Retry-After": "60" })
    : undefined;
}

// `brand/` holds the public marks that emails load (Ember review): mail clients fetch them with no session.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|robots.txt|brand/).*)"],
};
