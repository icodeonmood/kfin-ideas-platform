"use client";

/**
 * C-WORTH: what an idea is worth, four measures, any mix (C-WORTH.view), and the reviewer's revision in place
 * (C-WORTH.edit, L-WORTH). The view is shared: lane C places it on Check it (S-05); the sharer's page shows the
 * reviewer's figures beside theirs.
 */
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ChoiceChips } from "@/components/ui/chips";
import { Field, FieldMsg } from "@/components/ui/field";
import type { Kind, OutsideTools, WorthResponse, WorthTile } from "@/lib/contracts";

export const KIND_LABELS: Partial<Record<Kind, string>> = {
  problem: "A problem to fix",
  business_idea: "A new business idea",
};
/** E-ENUMS.sorting `area`, as the editor offers them (C-WORTH.edit). */
export const WORTH_AREAS = [
  "Investor service",
  "Operations",
  "Distributor experience",
  "Corporate registry",
  "Technology",
];
const TOOLS: { value: OutsideTools; label: string }[] = [
  { value: "none", label: "None" },
  { value: "partly", label: "Partly" },
  { value: "fully", label: "Fully" },
];

export function WorthView({ kind, area, tiles }: { kind: Kind; area: string | null; tiles: WorthTile[] }) {
  return (
    <div className="wv">
      <div className="chips wv-chips">
        {KIND_LABELS[kind] ? <span className="chip">{KIND_LABELS[kind]}</span> : null}
        {area ? <span className="chip">{area}</span> : null}
      </div>
      <dl className="wv-tiles">
        {tiles.map((t) => (
          <div key={t.measure} className={`tile sm${t.changed ? " wv-changed" : ""}`}>
            <dt className="meta">{t.label}</dt>
            <dd className={t.value === "Not given" ? "wv-empty" : undefined}>{t.value}</dd>
            {t.was ? <dd className="meta wv-was">{t.was}</dd> : null}
          </div>
        ))}
      </dl>
    </div>
  );
}

type Errors = Partial<
  Record<"hours_month" | "cost_month" | "revenue_month" | "outside_tools" | "note" | "form", string>
>;

function figureOf(tiles: WorthTile[], measure: WorthTile["measure"]): string {
  const v = tiles.find((t) => t.measure === measure)?.value ?? "";
  return v === "Not given" ? "" : v.replace(/ (?:hours? )?a month$/, "").replace(/ a month$/, "");
}

function toolsOf(tiles: WorthTile[]): OutsideTools {
  const v = tiles.find((t) => t.measure === "outside_tools")?.value;
  return v === "Partly less reliance" ? "partly" : v === "Fully less reliance" ? "fully" : "none";
}

/** The reviewer's last revision as typed, from `WorthResponse.reviewer` (a figure's `text` less its unit). */
export type WorthInitial = {
  hours?: string;
  cost?: string;
  revenue?: string;
  tools?: OutsideTools;
  note?: string;
};

export function WorthEditor({
  ideaId,
  sharerFirstName,
  kind,
  area,
  tiles,
  initial,
  onCancel,
  onSaved,
}: {
  ideaId: string;
  sharerFirstName: string;
  kind: Kind;
  area: string | null;
  tiles: WorthTile[];
  /** Opens on the reviewer's own figures and note after a revision on this page (L-WORTH/2). */
  initial?: WorthInitial;
  onCancel: () => void;
  onSaved: (saved: WorthResponse) => void;
}) {
  const [hours, setHours] = useState(initial?.hours ?? figureOf(tiles, "hours_month"));
  const [cost, setCost] = useState(initial?.cost ?? figureOf(tiles, "cost_month"));
  const [revenue, setRevenue] = useState(initial?.revenue ?? figureOf(tiles, "revenue_month"));
  const [tools, setTools] = useState<OutsideTools>(initial?.tools ?? toolsOf(tiles));
  const [newKind, setKind] = useState<Kind>(kind === "business_idea" ? "business_idea" : "problem");
  const [newArea, setArea] = useState(area ?? WORTH_AREAS[0]!);
  const [note, setNote] = useState(initial?.note ?? "");
  const [errors, setErrors] = useState<Errors>({});
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    setErrors({});
    try {
      const res = await fetch(`/api/desk/ideas/${encodeURIComponent(ideaId)}/worth`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hours_month: hours,
          cost_month: cost,
          revenue_month: revenue,
          outside_tools: tools,
          kind: newKind,
          area: newArea,
          note: note.trim() || undefined,
        }),
      });
      const body = (await res.json()) as WorthResponse | { error: { field?: string; message: string } };
      if (!res.ok || "error" in body) {
        const e = "error" in body ? body.error : { message: "That didn’t save. Try again." };
        setErrors({ [(e as { field?: string }).field ?? "form"]: e.message } as Errors);
        return;
      }
      onSaved(body);
    } catch {
      setErrors({ form: "That didn’t save. Try again." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="wv-edit"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <div className="wv-fields">
        <Field label="Hours a month" optional error={errors.hours_month}>
          {(p) => (
            <input {...p} value={hours} onChange={(e) => setHours(e.target.value)} placeholder="70 to 150" />
          )}
        </Field>
        <Field label="Cost a month" optional error={errors.cost_month}>
          {(p) => (
            <input
              {...p}
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              placeholder="about ₹25,000"
            />
          )}
        </Field>
        <Field label="Revenue a month" optional error={errors.revenue_month}>
          {(p) => <input {...p} value={revenue} onChange={(e) => setRevenue(e.target.value)} />}
        </Field>
      </div>
      <ChoiceChips
        label="Outside tools"
        options={TOOLS}
        value={tools}
        onChange={(v) => setTools(v as OutsideTools)}
      />
      <ChoiceChips
        label="What kind it is"
        options={[
          { value: "problem", label: "A problem to fix" },
          { value: "business_idea", label: "A new business idea" },
        ]}
        value={newKind}
        onChange={(v) => setKind(v as Kind)}
      />
      <ChoiceChips
        label="Area"
        options={WORTH_AREAS.map((a) => ({ value: a, label: a }))}
        value={newArea}
        onChange={setArea}
        scroll
      />
      <Field label="Note" optional multiline error={errors.note}>
        {(p) => (
          <textarea
            {...p}
            rows={2}
            maxLength={280}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="For example, the 40 calls are across three branches, so I scaled it up"
          />
        )}
      </Field>
      {errors.form ? <FieldMsg kind="error">{errors.form}</FieldMsg> : null}
      <div className="wv-actions">
        <p className="meta">{sharerFirstName} sees what you changed, with your note.</p>
        <Button type="button" variant="text" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" busy={busy} busyLabel="Saving…">
          Save
        </Button>
      </div>
    </form>
  );
}
