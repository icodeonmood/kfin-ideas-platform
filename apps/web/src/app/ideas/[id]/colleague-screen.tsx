"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Status } from "@/components/status";
import {
  errorFrom,
  TEAMUP_COPY,
  teamUpOpener,
  teamupUrls,
  useTeamUpSheet,
} from "@/components/teamup/teamup-sheet";
import { Avatar } from "@/components/ui/avatar";
import { Button, ButtonLink } from "@/components/ui/button";
import { Pill } from "@/components/ui/pill";
import { Track } from "@/components/ui/track";
import type { ColleagueView, PublicIdea } from "@/lib/contracts/api";

import { KeptBackLink } from "./parts";
import { toTrack, type StageWords } from "./track";

/** The phone board says the summary's note shorter (PhoneIdea.md); the words after it are the server's. */
const DESK_NOTE = "This is the short summary everyone at KFintech sees.";
const PHONE_NOTE = "The short summary everyone sees.";

/**
 * S-09, a colleague's idea (copy: reference/copy/Idea.md, PhoneIdea.md): the short summary, where it is, and Team
 * up. It renders only what the API sends a colleague (S-09.rules/1, DEC-104): never raw words, answers, files or a
 * decision's reason. A withdrawn idea, for someone who was on its crew, is its reference and one line (BLD-E011).
 */
export function ColleagueScreen({ view }: { view: ColleagueView }) {
  const { page } = view;
  if (page.state === "withdrawn" || !("title" in view.idea)) {
    return (
      <div className="ip ip-col">
        <KeptBackLink label={page.back.label} to={page.back.to} />
        <header className="ip-head">
          <Pill variant={page.pill.variant}>{page.pill.label}</Pill>
          <h1 className="h1 ip-title">{view.idea.ref ?? "This idea"}</h1>
        </header>
        <p className="ip-closed" role="status">
          {page.team_up.line}
        </p>
      </div>
    );
  }
  const idea = view.idea as PublicIdea & { stages: StageWords[] };
  const track = toTrack(idea.stages);
  const note = page.summary_note ?? "";
  return (
    <div className="ip ip-col">
      <KeptBackLink label={page.back.label} to={page.back.to} />

      <header className="ip-head">
        <p className="ip-ref ip-phone">{idea.ref}</p>
        <Pill variant={page.pill.variant}>{page.pill.label}</Pill>
        <h1 className="h1 ip-title">{idea.title}</h1>
        <p className="ip-ref ip-desk">{idea.ref}</p>
        {page.shared_line ? <p className="ip-meta">{page.shared_line}</p> : null}
      </header>

      <div className="ip-col-body">
        <section className="ip-sec ip-problem" aria-labelledby="ip-problem-h">
          <h2 id="ip-problem-h" className="ip-h2 ip-desk-h">
            {page.summary_heading ?? "The problem"}
          </h2>
          <p className="ip-summary">{idea.summary}</p>
          {note ? (
            <p className="ip-note">
              <span className="ip-desk">{note}</span>
              <span className="ip-phone">
                {note.startsWith(DESK_NOTE) ? PHONE_NOTE + note.slice(DESK_NOTE.length) : note}
              </span>
            </p>
          ) : null}
        </section>

        {/* Team up comes straight after the summary in the page's order, as both boards read it on a phone and in
            one column (PhoneIdea.md; WCAG 1.3.2); the desktop grid places it beside the summary. */}
        <TeamUpCard ideaId={idea.id} t={page.team_up} />

        {track ? (
          <section className="ip-sec ip-where" aria-labelledby="ip-where-h">
            <h2 id="ip-where-h" className="ip-h2">
              Where it is
            </h2>
            <Track stages={track} />
          </section>
        ) : null}

        {page.about?.length ? (
          <section className="ip-sec ip-about" aria-labelledby="ip-about-h">
            <h2 id="ip-about-h" className="ip-h2">
              About this idea
            </h2>
            <dl className="ip-dl">
              {page.about.map((r) => (
                <div key={r.label} className="ip-dl-row">
                  <dt>{r.label}</dt>
                  <dd>{r.value}</dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}
      </div>
    </div>
  );
}

type TeamUpWords = ColleagueView["page"]["team_up"];

/**
 * S-09's Team up card (S-09.layout/6, S-09.states, S-09.rules/2; J-TEAMUP/1-3; copy: Idea.md, PhoneIdea.md), drawn
 * from the state the API sends (`page.team_up.state`, worker `ideapage/colleague.py`), never guessed here:
 * - not asked: "Team up" opens lane F's C-SHEET-TEAMUP, named "Team up with {lead first name}";
 * - request sent: "Waiting for {lead}" with Withdraw, then "{lead} reads your note and decides. …";
 * - on the crew: "You're on the crew. …" and "Say hello", the way into the conversation (S-08). The API sends that
 *   link to the idea's crew alone, and the card shows it only in that state (non-negotiable 7, P-PRODUCT.privacy);
 * - closed or merged: one line instead of Team up, with a link to the surviving idea when merged (S-09.rules/2).
 * After a send or a withdraw the page is read again, so the card always says what the API says.
 */
export function TeamUpCard({ ideaId, t }: { ideaId: string; t: TeamUpWords }) {
  const router = useRouter();
  const heading = useRef<HTMLHeadingElement>(null);
  const teamUpButton = useRef<HTMLButtonElement>(null);
  const [busy, setBusy] = useState(false);
  // The request withdrawn here: Withdraw stays busy until the page reads a new state, so a second press never sends
  // a second DELETE against the request already gone
  const [withdrawn, setWithdrawn] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const ask = t.state === "not_asked" && t.can_team_up && t.action?.op === "teamup.open" ? t.action : null;
  const sent = t.state === "request_sent" ? t : null;
  const withdrawId = sent && sent.action?.op === "teamup.withdraw" ? sent.action.request_id : undefined;
  const crewLink = t.state === "on_crew" && t.action?.to ? { label: t.action.label, to: t.action.to } : null;
  const stateKey = `${t.state}:${withdrawId ?? ""}`;
  const waiting = busy || (withdrawId !== undefined && withdrawn === withdrawId);

  // After a withdraw the control that was pressed goes. Once the page has its new state, focus goes to "Team up",
  // back where Withdraw was, or to the card's heading when there is no Team up (the lead had answered first)
  // (WCAG 2.4.3). `refocusFrom` is the state the withdraw started from; a page read that still shows a request
  // waiting (a send read back before its withdraw) waits for the next one.
  const refocusFrom = useRef<string | null>(null);
  useEffect(() => {
    const from = refocusFrom.current;
    if (from === null || from === stateKey) return;
    if (ask) {
      refocusFrom.current = null;
      teamUpButton.current?.focus();
    } else if (t.state === "request_sent") {
      refocusFrom.current = stateKey;
    } else {
      refocusFrom.current = null;
      heading.current?.focus();
    }
  }, [stateKey, ask, t.state]);

  const teamUp = useTeamUpSheet({
    onSent: () => router.refresh(),
    onWithdrawn: () => {
      refocusFrom.current = stateKey;
      router.refresh();
    },
  });

  const withdraw = async () => {
    if (!withdrawId || waiting) return;
    const from = stateKey;
    setBusy(true);
    setFailed(null);
    try {
      const res = await fetch(teamupUrls.request(withdrawId), {
        method: "DELETE",
        credentials: "same-origin",
        headers: { accept: "application/json" },
      });
      if (res.ok) {
        setWithdrawn(withdrawId);
        refocusFrom.current = from;
        router.refresh();
        return;
      }
      const body: unknown = await res.json().catch(() => null);
      // NOT DRAWN (BLD-E046): HR sign-off. The API's own message, as the sheet shows it (BLD-F073); nothing is
      // logged (non-negotiable 3)
      setFailed(errorFrom(res.status, body).message);
      if (res.status === 404 || res.status === 409) {
        // The lead answered first, or the request has gone: the message stays, and the card is read again so it
        // shows where things stand
        refocusFrom.current = from;
        router.refresh();
      }
    } catch {
      // NOT DRAWN (BLD-E046): HR sign-off
      setFailed(TEAMUP_COPY.offline);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="ip-sec ip-team card" aria-labelledby="ip-team-h">
      <h2 id="ip-team-h" ref={heading} tabIndex={-1} className="ip-h2">
        Team up on this idea
      </h2>
      {t.count_line ? <p className="ip-team-count">{t.count_line}</p> : null}
      {t.faces?.length ? (
        <ul className="ip-faces" aria-label="The crew">
          {t.faces.map((p) => (
            <li key={p.id}>
              <Avatar initials={p.initials} size={36} name={p.name} ring="neutral" />
            </li>
          ))}
        </ul>
      ) : null}
      {sent && (sent.heading || withdrawId) ? (
        <div className="ip-team-wait">
          {sent.heading ? <p>{sent.heading}</p> : null}
          {withdrawId ? (
            // Stands where "Team up" was, so the sheet gives focus back to it on close (BLD-F074)
            <Button
              variant="text"
              busy={waiting}
              // NOT DRAWN (BLD-E046): HR sign-off. Idea.md draws no busy word; this is the sheet's
              busyLabel={TEAMUP_COPY.withdrawing}
              onClick={() => void withdraw()}
              {...teamUpOpener(ideaId)}
            >
              {sent.action?.label}
            </Button>
          ) : null}
        </div>
      ) : null}
      <p className={t.state === "on_crew" ? "ip-team-line ip-ok" : "ip-team-line"} role="status">
        {t.line}
      </p>
      {/* NOT DRAWN (BLD-E046): HR sign-off. The API's error line, or the offline line, after a refused withdraw */}
      {failed ? <Status kind="error" title={failed} role="alert" className="ip-team-err" /> : null}
      {t.link ? (
        <ButtonLink href={t.link.to} variant="line" aria-label={t.link.accessible_name}>
          {t.link.label}
        </ButtonLink>
      ) : null}
      {crewLink ? (
        <div className="ip-dock">
          <ButtonLink href={crewLink.to} variant="line">
            {crewLink.label}
          </ButtonLink>
        </div>
      ) : null}
      {ask ? (
        <div className="ip-dock">
          <Button
            ref={teamUpButton}
            variant="primary"
            aria-haspopup="dialog"
            onClick={() => teamUp.open(ideaId)}
          >
            {ask.label}
          </Button>
        </div>
      ) : null}
      {teamUp.sheet}
    </section>
  );
}
