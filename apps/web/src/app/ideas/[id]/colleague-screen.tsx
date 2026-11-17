import Link from "next/link";

import { Avatar } from "@/components/ui/avatar";
import { ButtonLink } from "@/components/ui/button";
import { Pill } from "@/components/ui/pill";
import { Track } from "@/components/ui/track";
import type { ColleagueView, PublicIdea } from "@/lib/contracts/api";

import { toTrack, type StageWords } from "./track";

/** The phone board says the summary's note shorter (PhoneIdea.md); the words after it are the server's. */
const DESK_NOTE = "This is the short summary everyone at KFintech sees.";
const PHONE_NOTE = "The short summary everyone sees.";

export function BackLink({ label, to }: { label: string; to: string }) {
  const short = label.replace(/^Back to (the )?/, "");
  return (
    <Link className="back ip-back" href={to} aria-label={label}>
      <span className="ip-desk">{label}</span>
      <span className="ip-phone">{short}</span>
    </Link>
  );
}

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
        <BackLink label={page.back.label} to={page.back.to} />
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
  const t = page.team_up;
  const note = page.summary_note ?? "";
  return (
    <div className="ip ip-col">
      <BackLink label={page.back.label} to={page.back.to} />

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

        <section className="ip-sec ip-team card" aria-labelledby="ip-team-h">
          <h2 id="ip-team-h" className="ip-h2">
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
          {t.state === "request_sent" && t.heading ? <p className="ip-team-wait">{t.heading}</p> : null}
          <p className={t.state === "on_crew" ? "ip-team-line ip-ok" : "ip-team-line"} role="status">
            {t.line}
          </p>
          {t.link ? (
            <ButtonLink href={t.link.to} variant="line" aria-label={t.link.accessible_name}>
              {t.link.label}
            </ButtonLink>
          ) : null}
          {t.action?.to ? (
            <div className="ip-dock">
              <ButtonLink href={t.action.to} variant={t.state === "on_crew" ? "line" : "primary"}>
                {t.action.label}
              </ButtonLink>
            </div>
          ) : null}
          {/* TODO(lane F): C-SHEET-TEAMUP. "Team up" (op teamup.open) opens lane F's sheet and "Withdraw" on a sent
              request is lane F's op; both are left out until the sheet and its endpoints land (S-09.states). */}
        </section>
      </div>
    </div>
  );
}
