"use client";

import { useState } from "react";

import { Button, ButtonLink } from "@/components/ui/button";
import { ChoiceChips, MultiChips } from "@/components/ui/chips";
import { Dropdown } from "@/components/ui/dropdown";
import { Empty } from "@/components/ui/empty";
import { Field } from "@/components/ui/field";
import { DropArea, FileList, FileRow } from "@/components/ui/file";
import { SearchBar } from "@/components/ui/search";
import { IDEA_STATUS, Pill, StatusPill, type IdeaStatus } from "@/components/ui/pill";
import { Skeleton, SkeletonRows } from "@/components/ui/skeleton";
import { Sorts } from "@/components/ui/sorts";
import { tabPanelProps, Tabs } from "@/components/ui/tabs";
import { Track } from "@/components/ui/track";

const AREAS = [
  { value: "investor", label: "Investor service", count: 12 },
  { value: "distributor", label: "Distributor service", count: 7 },
  { value: "ops", label: "Transaction operations", count: 4 },
  { value: "tech", label: "Technology", count: 0 },
];

export function KitDemo() {
  const [area, setArea] = useState<string | null>("investor");
  const [worth, setWorth] = useState<string[]>(["time"]);
  const [sort, setSort] = useState("latest");
  const [tab, setTab] = useState("yours");
  const [busy, setBusy] = useState(false);
  const [title, setTitle] = useState("");
  const [tried, setTried] = useState(false);
  const short = title.trim().length < 30;
  const [q, setQ] = useState("");
  const [qf, setQf] = useState<string[]>(["needs"]);
  const [along, setAlong] = useState<string[]>([]);

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
            onClick={() => {
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
              text: "Found a phone number on page 2. Nobody can open it until it’s hidden.",
            }}
          >
            <button type="button" className="tb">
              Hide it for me
            </button>
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
