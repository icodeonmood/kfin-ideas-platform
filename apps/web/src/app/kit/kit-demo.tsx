"use client";

import { useRef, useState } from "react";

import { Prompt, PROMPT_COPY, type PromptVoice } from "@/components/compose/prompt";
import { AttachButton } from "@/components/ui/attach-button";
import { Avatar, CrewFaces } from "@/components/ui/avatar";
import { Button, ButtonLink } from "@/components/ui/button";
import { ChoiceChips, MultiChips } from "@/components/ui/chips";
import { CodeField } from "@/components/ui/code-field";
import { Deck } from "@/components/ui/deck";
import { Dropdown } from "@/components/ui/dropdown";
import { Empty } from "@/components/ui/empty";
import { Field } from "@/components/ui/field";
import { DropArea, FileList, FileRemove, FileRow } from "@/components/ui/file";
import { OnesEmpty, OnesFan, OnesNext, OnesPost } from "@/components/ui/ones-fan";
import { QuestionBox } from "@/components/ui/question-box";
import { SearchBar } from "@/components/ui/search";
import { IDEA_STATUS, Pill, StatusPill, type IdeaStatus } from "@/components/ui/pill";
import { Skeleton, SkeletonRows } from "@/components/ui/skeleton";
import { Sorts } from "@/components/ui/sorts";
import { tabPanelProps, Tabs } from "@/components/ui/tabs";
import { Track } from "@/components/ui/track";
import { sparkBurst } from "@/lib/motion/spark";

const AREAS = [
  { value: "investor", label: "Investor service", count: 12 },
  { value: "distributor", label: "Distributor service", count: 7 },
  { value: "ops", label: "Transaction operations", count: 4 },
  { value: "tech", label: "Technology", count: 0 },
];

/** The kit's microphone: drawn, never recording (the prompt box is lane C's; here it only stands beside "+"). */
const KIT_VOICE: PromptVoice = {
  state: { status: "idle", notice: null },
  start() {},
  stop() {},
  noticeShown() {},
};

export function KitDemo() {
  const [area, setArea] = useState<string | null>("investor");
  const [worth, setWorth] = useState<string[]>(["time"]);
  const [sort, setSort] = useState("latest");
  const [tab, setTab] = useState("yours");
  const [cheered, setCheered] = useState<number[]>([9]);
  const [busy, setBusy] = useState(false);
  const [title, setTitle] = useState("");
  const [tried, setTried] = useState(false);
  const short = title.trim().length < 30;
  const [q, setQ] = useState("");
  const [qf, setQf] = useState<string[]>(["needs"]);
  const [along, setAlong] = useState<string[]>([]);
  const [deckAt, setDeckAt] = useState(0);
  const [code, setCode] = useState("");
  const [codeWrong, setCodeWrong] = useState(false);
  const [pin, setPin] = useState("problem");
  const [asked, setAsked] = useState<string[]>([]);
  const [requested, setRequested] = useState(false);
  const teamUpRef = useRef<HTMLButtonElement>(null);
  const [words, setWords] = useState("");
  const [picking, setPicking] = useState(false);

  return (
    <div className="arrive kit">
      <h1 className="h1">Components</h1>
      <p className="lead">Every shared component in its states, with made-up content. Dev and test only.</p>

      <section className="card" aria-labelledby="k-buttons">
        <h2 id="k-buttons" className="h2">
          Buttons
        </h2>
        <div className="btn-row">
          <Button variant="line">Back</Button>
          <Button
            busy={busy}
            busyLabel="Sending…"
            onClick={(e) => {
              sparkBurst(e.currentTarget);
              setBusy(true);
              window.setTimeout(() => setBusy(false), 2_000);
            }}
          >
            Send it
          </Button>
          <Button variant="soft" size="sm">
            Show 5 more
          </Button>
          <Button variant="text">Open the full idea</Button>
          <Button variant="text-blue">See the similar idea</Button>
          <Button disabled>Move to Check it</Button>
          <ButtonLink href="/kit#k-fields" variant="line" size="sm">
            Jump to fields
          </ButtonLink>
        </div>
      </section>

      <section className="card" aria-labelledby="k-quiet-h" id="k-quiet">
        <h2 id="k-quiet-h" className="h2">
          Requested and Withdraw
        </h2>
        <p className="meta">Requested, beside a normal Team up, in two variants.</p>
        <div className="btn-row">
          <Button>Team up</Button>
          <Button inactive>Requested</Button>
          <Button variant="line" size="sm" inactive>
            Requested
          </Button>
        </div>
        <p className="meta">The quiet link, as a link and as a button, at rest and focused.</p>
        <div className="btn-row">
          <a href="/kit#k-quiet" className="link-quiet">
            How teaming up works
          </a>
          <Button variant="quiet">Withdraw</Button>
          <a href="/kit#k-quiet" className="link-quiet kit-focus">
            How teaming up works
          </a>
          <Button variant="quiet" className="kit-focus">
            Withdraw
          </Button>
        </div>
        <p className="meta">A crew card&rsquo;s foot: Team up, then Requested with Withdraw under it.</p>
        <div className="kit-stack" role="group" aria-label="A crew card’s foot">
          <Button ref={teamUpRef} size="full" inactive={requested} onClick={() => setRequested(true)}>
            {requested ? "Requested" : "Team up"}
          </Button>
          {requested ? (
            <Button
              variant="quiet"
              onClick={() => {
                setRequested(false);
                teamUpRef.current?.focus();
              }}
            >
              Withdraw
            </Button>
          ) : null}
        </div>
      </section>

      <section className="card" aria-labelledby="k-attach">
        <h2 id="k-attach" className="h2">
          Attach
        </h2>
        <p className="meta">
          The &ldquo;+&rdquo; button at rest, pressed (its picker open) and switched off.
        </p>
        <div className="btn-row">
          <AttachButton aria-expanded={false} />
          <AttachButton aria-expanded />
          <AttachButton disabled />
        </div>
        <p className="meta">In a prompt box&rsquo;s tool row: &ldquo;+&rdquo;, then the mic, then send.</p>
        <div className="cz">
          <Prompt
            value={words}
            onChange={setWords}
            onSend={() => setWords("")}
            sendLabel="Start my draft"
            label={PROMPT_COPY.firstLabel}
            placeholder="Describe what’s getting in your way"
            device="desktop"
            voice={KIT_VOICE}
            attach={
              <AttachButton
                aria-expanded={picking}
                aria-controls="k-picker"
                onClick={() => setPicking((open) => !open)}
              />
            }
          />
          <div id="k-picker" role="group" aria-label="Add files, a folder or a link" hidden={!picking}>
            <p className="meta">The screen&rsquo;s picker opens here (C-FILE.uploader).</p>
          </div>
        </div>
      </section>

      <section className="card" aria-labelledby="k-people">
        <h2 id="k-people" className="h2">
          People
        </h2>
        <div className="btn-row">
          <Avatar initials="AS" size={44} name="Asha Shetty" />
          <Avatar initials="AS" size={36} ring="neutral" name="Asha Shetty" />
          <Avatar initials="AS" size={36} tier={4} name="Asha Shetty, Tier 4, Blaze" />
          <Avatar initials="" size={36} system name="1% Club" />
        </div>
        <CrewFaces
          leadName="Rahul Verma"
          total={5}
          people={[
            { name: "Rahul Verma", initials: "RV" },
            { name: "Asha Shetty", initials: "AS" },
            { name: "Imran Qureshi", initials: "IQ" },
            { name: "Leela Das", initials: "LD" },
          ]}
        />
      </section>

      <section className="card" aria-labelledby="k-pills">
        <h2 id="k-pills" className="h2">
          Status pills
        </h2>
        <div className="btn-row">
          {(Object.keys(IDEA_STATUS) as IdeaStatus[]).map((s) => (
            <StatusPill key={s} status={s} />
          ))}
          <Pill variant="bad">Couldn’t upload</Pill>
          <Pill variant="soon">Coming soon</Pill>
        </div>
        <div className="btn-row">
          <Pill countdown>3 days to answer</Pill>
          <Pill variant="warn" countdown>
            07:38 to answer
          </Pill>
          <Pill variant="bad" countdown>
            Overdue by 5 hours
          </Pill>
          <Pill variant="ok" countdown>
            Picked, 2 November
          </Pill>
        </div>
      </section>

      <section className="card" aria-labelledby="k-fields-h" id="k-fields">
        <h2 id="k-fields-h" className="h2">
          Fields
        </h2>
        <div className="kit-cols">
          <Field
            label="Title"
            help={`${title.trim().length} of at least 30 characters`}
            error={tried && short ? "Add a few more words so the review desk can follow it." : undefined}
          >
            {(p) => (
              <input
                {...p}
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  setTried(false); // typing clears the message at once (C-FIELD.rules/4)
                }}
                onBlur={() => setTried(true)}
                placeholder="Investors call to ask why a redemption was rejected"
              />
            )}
          </Field>
          <Field
            label="Anything else the desk should know"
            optional
            multiline
            warning="This mentions a folio number. We hid it."
          >
            {(p) => <textarea {...p} rows={4} defaultValue="Folio ••••89 asked twice this week." />}
          </Field>
        </div>
      </section>

      <section className="card" aria-labelledby="k-kinds">
        <h2 id="k-kinds" className="h2">
          The code and the question box
        </h2>
        <CodeField
          label="The 6-digit code from the email"
          value={code}
          onChange={(v) => {
            setCode(v);
            setCodeWrong(false);
          }}
          onComplete={(v) => setCodeWrong(v !== "246810")}
          error={
            codeWrong
              ? "That code didn’t match. Check the latest email from 1% Club. 2 tries left."
              : undefined
          }
        />
        <QuestionBox
          label="What would you like to ask Asha?"
          parts={[
            { value: "problem", label: "The problem" },
            { value: "often", label: "How often" },
            { value: "who", label: "Who it affects" },
            { value: "worth", label: "What it’s worth" },
            { value: "attached", label: "Attached" },
            { value: "fix", label: "Fix" },
          ]}
          pinned={pin}
          onPinned={setPin}
          onAdd={(q, part) => setAsked((a) => [...a, `${part}: ${q}`])}
        />
        {asked.length ? (
          <ul className="meta" aria-label="Your questions">
            {asked.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="card" aria-labelledby="k-chips">
        <h2 id="k-chips" className="h2">
          Chips
        </h2>
        <p className="meta" id="k-area">
          Area, pick one
        </p>
        <ChoiceChips label="Area" options={AREAS} value={area} onChange={setArea} scroll />
        <p className="meta">What it would bring, pick all that apply</p>
        <MultiChips
          label="What it would bring"
          options={[
            { value: "time", label: "Saves time" },
            { value: "cost", label: "Saves cost" },
            { value: "revenue", label: "Brings revenue" },
          ]}
          values={worth}
          onChange={setWorth}
        />
      </section>

      <section className="card" aria-labelledby="k-lists">
        <h2 id="k-lists" className="h2">
          Tabs, sorts, empty states and loading
        </h2>
        <Tabs
          id="k-tabs"
          label="Your ideas"
          tabs={[
            { value: "yours", label: "Yours", count: 3 },
            { value: "teamed", label: "Teamed up", count: 0 },
          ]}
          value={tab}
          onChange={setTab}
        />
        <div className="kit-row">
          <Sorts
            options={[
              { value: "latest", label: "Latest activity" },
              { value: "shared", label: "Date shared" },
              { value: "stage", label: "Stage" },
            ]}
            value={sort}
            onChange={setSort}
          />
        </div>
        <div {...tabPanelProps("k-tabs", tab)}>
          {tab === "yours" ? (
            <SkeletonRows what="Loading your ideas" />
          ) : (
            <Empty
              title="Nothing teamed up yet"
              action={
                <ButtonLink href="/wall" variant="line" size="sm">
                  Browse the Wall
                </ButtonLink>
              }
            >
              When you team up on a colleague’s idea, it shows here.
            </Empty>
          )}
        </div>
      </section>

      <section className="card" aria-labelledby="k-search">
        <h2 id="k-search" className="h2">
          Search, dropdown and files
        </h2>
        <SearchBar
          label="Search your ideas"
          placeholder="Search your ideas, or ask a question"
          text={q}
          onText={setQ}
          filters={[
            { value: "needs", label: "Needs you", count: 1 },
            { value: "desk", label: "With the review desk", count: 2 },
            { value: "closed", label: "Closed", count: 0 },
          ]}
          picked={qf}
          onPicked={setQf}
          onSubmit={() => undefined}
          asks={["Which of my ideas need me this week?", "What did the review desk pick?"]}
          foot="Search reads your titles, your own words, your files and the review desk’s notes."
        />
        <Dropdown
          label="Bring your ideas along"
          noun={{ one: "idea", many: "ideas" }}
          options={[
            { value: "a", title: "Rejection SMS codes confuse investors", meta: "Shared Friday" },
            { value: "b", title: "No script for calls about rejections", meta: "Draft, Wednesday" },
          ]}
          values={along}
          onChange={setAlong}
        />
        <FileList label="Your files">
          <FileRow name="rejection-sms.png" size="240 KB" status="checked" statusText="Checked">
            <button type="button" className="tb">
              View
            </button>
            <button type="button" className="tb">
              Remove
            </button>
          </FileRow>
          <FileRow
            name="branch-calls.xlsx"
            size="1.2 MB"
            status="checking"
            statusText="Checking for personal details"
          >
            <button type="button" className="tb">
              Remove
            </button>
          </FileRow>
          <FileRow
            name="call-log.pdf"
            size="3.4 MB"
            status="found"
            statusText="Waiting for you"
            message={{
              kind: "warn",
              text: "Found a phone number on page 2. Only you, the review desk and the Ones Committee can open it.",
            }}
          >
            <button type="button" className="tb">
              Hide it for me
            </button>
          </FileRow>
        </FileList>
        {/* BLD-D030: the conversation box's compact rows (Messages.md `.cvfile`): one waiting while the check is off,
            with no spinner (BLD-C237), and one with an error on its own line */}
        <FileList label="Files in your message" compact>
          <FileRow name="branch-notes.md" size="2 KB" status="checked" statusText="Checked">
            <FileRemove label="Remove branch-notes.md" onClick={() => undefined} />
          </FileRow>
          <FileRow
            name="call-log-week-47.pdf"
            size="3.4 MB"
            status="checking"
            statusText="Waiting for the personal details check. It runs when the assistant is back."
            waiting
          >
            <FileRemove label="Remove call-log-week-47.pdf" onClick={() => undefined} />
          </FileRow>
          <FileRow
            name="rejection-sms-screens.png"
            size="16 MB"
            status="too-big"
            statusText=""
            message={{ kind: "error", text: "Too big. Files can be up to 15 MB." }}
          >
            <FileRemove label="Remove rejection-sms-screens.png" onClick={() => undefined} />
          </FileRow>
        </FileList>
        <DropArea
          title="Drop files here, or"
          browse={
            <button type="button" className="tb blue">
              browse
            </button>
          }
          help="Screenshots, photos, PDFs or spreadsheets, up to 25 MB each."
        />
      </section>

      <section className="card" aria-labelledby="k-deck">
        <h2 id="k-deck" className="h2">
          Deck
        </h2>
        <Deck
          label="Ideas close to yours"
          index={deckAt}
          onIndexChange={setDeckAt}
          cards={[
            "Rejection SMS codes confuse investors",
            "No script for calls about rejections",
            "Branch queue times are not tracked anywhere",
          ].map((t) => (
            <article key={t} className="card kit-dcard">
              <StatusPill status="with_review_desk" />
              <h3 className="h3">{t}</h3>
              <p className="meta">Investor service, Hyderabad</p>
              <Button size="full">Team up</Button>
            </article>
          ))}
        />
      </section>

      <section className="card" aria-labelledby="k-fan">
        <h2 id="k-fan" className="h2">
          The Ones
        </h2>
        {/* C-ONES-FAN.states on the slab it is drawn for: none, one with its companion (cheered), several stacked
            (See details or a first move spreads it) */}
        <div className="kit-slab">
          <div>
            <h3 className="kit-slab-h">None</h3>
            <OnesFan
              label="No posts from the Ones"
              cards={[]}
              empty={
                <OnesEmpty
                  title="No Ones yet"
                  body="When a shared fix ships and its result is measured, the people behind it are posted here first."
                />
              }
              companion={null}
            />
          </div>
          <div>
            <h3 className="kit-slab-h">One</h3>
            <OnesFan
              label="One post from the Ones"
              empty={null}
              companion={
                <OnesNext
                  title="The next One could be you"
                  body="Every fix here started with one person saying what kept going wrong."
                  action="Share a problem"
                  href="/kit#k-fan"
                />
              }
              cards={[
                <OnesPost
                  key={9}
                  name="Neha Kapoor"
                  initials="NK"
                  number={9}
                  tier={5}
                  tierName="White heat"
                  ago="1w"
                  sentence="Redemption requests now show a live status, so investors can see where their money is without calling."
                  figure="52%"
                  unit="fewer calls asking where the money is"
                  cheers={98 + (cheered.includes(9) ? 1 : 0)}
                  cheered={cheered.includes(9)}
                  onCheer={() => setCheered((c) => (c.includes(9) ? c.filter((n) => n !== 9) : [...c, 9]))}
                  replies={12}
                  threadHref="/kit#k-fan"
                />,
              ]}
            />
          </div>
          <div>
            <h3 className="kit-slab-h">Several</h3>
            <OnesFan
              empty={null}
              companion={null}
              people={3}
              cards={[
                {
                  n: 1,
                  t: 4,
                  tn: "Blaze",
                  who: "Asha Shetty",
                  i: "AS",
                  f: "1,240",
                  u: "failed debits avoided last quarter",
                },
                { n: 17, t: 2, tn: "Glow", who: null, i: "", f: "38%", u: "fewer calls about rejections" },
                {
                  n: 5,
                  t: 6,
                  tn: "Blue flame",
                  who: "Imran Qureshi",
                  i: "IQ",
                  f: "6 hrs",
                  u: "saved each week at one branch",
                },
              ].map((p) => (
                <OnesPost
                  key={p.n}
                  name={p.who}
                  initials={p.i}
                  number={p.n}
                  tier={p.t}
                  tierName={p.tn}
                  ago="2d"
                  sentence="Rejection messages now say what went wrong and what to do next."
                  adopted="Adopted by 3 teams"
                  figure={p.f}
                  unit={p.u}
                  cheers={24 + (cheered.includes(p.n) ? 1 : 0)}
                  cheered={cheered.includes(p.n)}
                  onCheer={() =>
                    setCheered((c) => (c.includes(p.n) ? c.filter((n) => n !== p.n) : [...c, p.n]))
                  }
                  replies={6}
                  threadHref="/kit#k-fan"
                />
              ))}
            />
          </div>
        </div>
      </section>

      <section className="card" aria-labelledby="k-track">
        <h2 id="k-track" className="h2">
          Where it is
        </h2>
        <Track
          stages={{
            shared: { state: "done", line: "Today, 10:05 am" },
            checked: { state: "done", line: "Personal details hidden, 2 similar ideas found" },
            reviewed: { state: "now", line: "By Friday 20 November" },
            built: { state: "next", line: "If it’s picked" },
            shipped: { state: "next", line: "Then we measure what changed" },
          }}
        />
      </section>

      <section aria-labelledby="k-surfaces" className="kit-surfaces">
        <h2 id="k-surfaces" className="h2">
          Surfaces
        </h2>
        <div className="panel">
          <h3 className="h3">Glass panel</h3>
          <p className="body">Side panels, players and filter panels.</p>
        </div>
        <div className="note">A note explains something in place.</div>
        <div className="note blue">A blue note points at something related.</div>
        <div className="placeholder">
          <Pill variant="soon">Coming soon</Pill>
        </div>
        <div className="card">
          <Skeleton width="60%" height={18} />
          <Skeleton width="90%" style={{ marginTop: 12 }} />
          <Skeleton width="70%" style={{ marginTop: 8 }} />
        </div>
      </section>
    </div>
  );
}
