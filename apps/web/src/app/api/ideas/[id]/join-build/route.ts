import { writeRoute } from "@/server/desk";

/**
 * POST /api/ideas/{id}/join-build — "Ask to join the build team" (A-API, L-DECIDE.rules/6, DEC-111). Signed in; the
 * worker checks the rest: the sharer or crew, after a Pick that stands, until the team is chosen. No body. Answers
 * `JoinBuildResponse` (`{ asked_at }`, the same on a repeat), or 403 forbidden, 404 not_found, 409 not_picked or
 * 409 team_chosen in the pack's error shape.
 */
export const POST = writeRoute("signed_in", "POST", (id) => `/internal/ideas/${id}/join-build`);
