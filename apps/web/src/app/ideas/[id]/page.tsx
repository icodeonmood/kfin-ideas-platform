import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { NextRequest } from "next/server";

import type {
  ColleagueView,
  DecisionForViewerResponse,
  IdeaViewResponse,
  SharerQuestionSetResponse,
  SharerView,
} from "@/lib/contracts/api";
import { Status } from "@/components/status";
import { currentUser } from "@/server/auth/current";
import { getRoute } from "@/server/desk";
import { getIdeaView } from "@/server/idea-page";

import { ColleagueScreen } from "./colleague-screen";
import { WayBack, type Carried } from "./parts";
import { SharerScreen } from "./sharer-screen";

import "./idea-page.css";

export const metadata: Metadata = { title: "Idea" };
export const dynamic = "force-dynamic";

const LOAD_FAILED = "We can't load this idea just now. Please try again in a minute.";

// Lane B's two endpoints S-06 composes (BLD-E012): the decision with its reason and the committee's window, and the
// open question set
const decisionRoute = getRoute("signed_in", (id) => `/internal/ideas/${id}/decision`);
const questionSetRoute = getRoute("signed_in", (id) => `/internal/ideas/${id}/question-set`);

function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

async function readJson<T>(res: Response): Promise<T | null> {
  if (!res.ok) return null;
  try {
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/** What lane B adds to the sharer's page: read only when the page says its card is composed from it. */
async function laneB(view: SharerView): Promise<{
  decision: DecisionForViewerResponse;
  questions: SharerQuestionSetResponse;
  failed: boolean;
}> {
  const ctx = { params: Promise.resolve({ id: view.idea.ref ?? view.idea.id }) };
  const req = (path: string) => new NextRequest(new URL(path, "http://web.local"));
  const decided = ["picked", "not_now", "not_picked", "reversed", "being_built", "shipped"].includes(
    view.page.state,
  );
  const [d, q] = await Promise.all([
    decided || view.page.card_from === "decision"
      ? decisionRoute(req(view.page.lane_b.decision), ctx).catch(() => null)
      : null,
    view.page.card_from === "question_set" || view.idea.has_open_questions
      ? questionSetRoute(req(view.page.lane_b.question_set), ctx).catch(() => null)
      : null,
  ]);
  const decision = d ? await readJson<DecisionForViewerResponse>(d) : null;
  const questions = q ? await readJson<SharerQuestionSetResponse>(q) : null;
  const failed =
    (view.page.card_from === "decision" && !decision) ||
    (view.page.card_from === "question_set" && !questions);
  return { decision, questions, failed };
}

/**
 * `/ideas/:id` (P-ROUTES.screens): S-06 for the sharer, S-09 for anyone else, as the API decides (A-API.ideas); a
 * reviewer goes on to S-R2 and the owner's draft to where it was left. `from` and `back` say where the person came
 * from, so the page's own way back returns to that exact view (P-ROUTES.state); once read, they leave the address
 * and the way back is kept in the history entry (parts.tsx, BLD-E021).
 */
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const id = (await params).id;
  const me = await currentUser();
  if (!me) redirect(`/sign-in?next=${encodeURIComponent(`/ideas/${id}`)}`);
  const sp = await searchParams;
  const q = new URLSearchParams();
  const from = one(sp.from);
  const back = one(sp.back);
  if (from) q.set("from", from.slice(0, 40));
  if (back) q.set("back", back.slice(0, 600));

  let view: IdeaViewResponse | null = null;
  let status = 0;
  try {
    const res = await getIdeaView(
      new NextRequest(new URL(`/api/ideas/${encodeURIComponent(id)}?${q.toString()}`, "http://web.local")),
      { params: Promise.resolve({ id }) },
    );
    status = res.status;
    if (res.ok) view = (await res.json()) as IdeaViewResponse;
  } catch {
    view = null;
  }
  if (status === 404) notFound();
  if (view && (view.view === "desk" || view.view === "draft")) redirect(view.to);

  // The address keeps `from` and `back` when the page cannot load, so a reload to try again still knows the way back
  if (!view) {
    return (
      <div className="ip">
        <h1 className="h1 ip-fail-h">Idea</h1>
        <Status kind="error" title={LOAD_FAILED} className="ip-fail" />
      </div>
    );
  }
  const carried: Carried = from === "share" ? "once" : from || back ? "keep" : null;
  if (view.view === "sharer") {
    const b = await laneB(view);
    const crumb = view.page.breadcrumb;
    return (
      <WayBack way={{ label: crumb.label, to: crumb.to }} carried={carried}>
        <SharerScreen view={view} decision={b.decision} questions={b.questions} partFailed={b.failed} />
      </WayBack>
    );
  }
  const colleague = view as ColleagueView;
  return (
    <WayBack way={{ label: colleague.page.back.label, to: colleague.page.back.to }} carried={carried}>
      <ColleagueScreen view={colleague} />
    </WayBack>
  );
}
