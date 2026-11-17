"use client";

import Link from "next/link";
import { useId, useRef, useState, type PointerEvent } from "react";

import { CountOnce } from "@/components/count-once";
import { Avatar } from "@/components/ui/avatar";
import { buttonClass } from "@/components/ui/button";
import { FieldMsg } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import type { ProfileResponse } from "@/lib/contracts/api";
import type { PersonSettings } from "@/lib/contracts/entities";
import { reducedMotion } from "@/lib/motion/flip";

import { ReferAsCard } from "./refer-as";
import { pointsText, REACH, SAVE_FAILED, switchState, WALL_LINE, type SwitchKey } from "./rules";

/**
 * C-SWITCH as S-H6.rules/5 draws it: `role="switch"` with `aria-checked`, labelled by its title and described by its
 * line (and by its message after a failed save). Disabled is `aria-disabled`, so it stays in the reading order.
 */
function SettingSwitch({
  title,
  line,
  on,
  disabled,
  soon,
  error,
  announce,
  onFlip,
}: {
  title: string;
  line: string;
  on: boolean;
  disabled?: boolean;
  soon?: boolean;
  error: string | null;
  /** The line is a live region: it changes with the switch and is said once (S-H6.layout/3, Profile.md `wall`). */
  announce?: boolean;
  onFlip: () => void;
}) {
  const id = useId();
  return (
    <div className="pf-row">
      <div className="pf-row-in">
        <div className="pf-txt">
          <p className="pf-l" id={`${id}-t`}>
            {title}
            {soon ? (
              <>
                {" "}
                <Pill variant="soon">Coming soon</Pill>
              </>
            ) : null}
          </p>
          <p className="pf-d" id={`${id}-d`} role={announce ? "status" : undefined}>
            {line}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          className="pf-sw"
          aria-checked={on}
          aria-labelledby={`${id}-t`}
          aria-describedby={[`${id}-d`, error ? `${id}-m` : ""].filter(Boolean).join(" ")}
          aria-disabled={disabled || undefined}
          onClick={() => {
            if (!disabled) onFlip();
          }}
        >
          <i aria-hidden="true" />
        </button>
      </div>
      {error ? <FieldMsg id={`${id}-m`}>{error}</FieldMsg> : null}
    </div>
  );
}

/** The head (S-H6.layout/1): a card that leans a little toward the pointer; still under reduced motion. */
function Head({ data }: { data: ProfileResponse }) {
  const card = useRef<HTMLElement>(null);
  const lean = (e: PointerEvent<HTMLElement>) => {
    const el = card.current;
    if (!el || e.pointerType !== "mouse" || reducedMotion()) return;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    el.style.setProperty("--pf-ry", `${(x * 4).toFixed(2)}deg`);
    el.style.setProperty("--pf-rx", `${(-y * 4).toFixed(2)}deg`);
  };
  const rest = () => {
    card.current?.style.removeProperty("--pf-ry");
    card.current?.style.removeProperty("--pf-rx");
  };
  return (
    <header ref={card} className="pf-head" onPointerMove={lean} onPointerLeave={rest}>
      <Avatar initials={data.avatar.initials} tier={data.avatar.tier} className="pf-av" />
      <div className="pf-who">
        <h1 className="pf-t">{data.person.name}</h1>
        <p className="pf-s">{data.line}</p>
        {data.one_dashboard ? (
          <p className="pf-one">
            <Link href={data.one_dashboard} className={buttonClass("text-blue")}>
              Your One dashboard
            </Link>
          </p>
        ) : null}
      </div>
    </header>
  );
}

/**
 * S-H6: who the person is in 1% Club, their private points, whether their name shows on the Wall, and how they are
 * reached. Every switch saves at once and shows its new state: no Save button, no toast (S-H6.rules/1). A failed
 * save flips the switch back with "Couldn't save that. Try again." under it. One column on a phone.
 */
export function ProfileScreen({ data }: { data: ProfileResponse }) {
  const [settings, setSettings] = useState<PersonSettings>(data.person.settings);
  const [errors, setErrors] = useState<Partial<Record<SwitchKey, string>>>({});
  const seq = useRef<Partial<Record<SwitchKey, number>>>({});
  const teamsOn = data.available.teams;

  const flip = async (key: SwitchKey) => {
    const next = !settings[key];
    const mine = (seq.current[key] ?? 0) + 1;
    seq.current[key] = mine;
    setSettings((s) => ({ ...s, [key]: next }));
    setErrors((e) => ({ ...e, [key]: undefined }));
    const res = await fetch("/api/me/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [key]: next }),
    }).catch(() => null);
    const body = (await res?.json().catch(() => null)) as {
      settings?: Partial<PersonSettings>;
      error?: { message?: string };
    } | null;
    if (seq.current[key] !== mine) return; // a later flip of the same switch decides
    const saved = res?.ok ? switchState(body?.settings, key) : undefined;
    if (saved !== undefined) {
      setSettings((s) => ({ ...s, [key]: saved }));
      return;
    }
    setSettings((s) => ({ ...s, [key]: !next }));
    setErrors((e) => ({ ...e, [key]: body?.error?.message || SAVE_FAILED }));
  };

  const points = pointsText(data.person.points);
  const onWall = settings.show_name_on_wall;

  return (
    <div className="pf">
      <Head data={data} />
      <div className="pf-grid">
        <section className="pf-card" aria-labelledby="pf-pt-h">
          <h2 id="pf-pt-h" className="pf-k">
            Your points
          </h2>
          <p className="num pf-num">
            <CountOnce value={points} />
          </p>
          <p className="pf-note">Only you see your points. They never decide who becomes a One.</p>
          <Link href="/how-it-works" className={buttonClass("text", "regular", "pf-more")}>
            How points and tiers work
          </Link>
        </section>
        <div className="pf-set">
          <section className="pf-card" aria-labelledby="pf-nw-h">
            <h2 id="pf-nw-h" className="pf-k">
              On the Wall
            </h2>
            <SettingSwitch
              title="Show my name next to my ideas"
              line={onWall ? WALL_LINE.on : WALL_LINE.off}
              on={onWall}
              announce
              error={errors.show_name_on_wall ?? null}
              onFlip={() => void flip("show_name_on_wall")}
            />
          </section>
          <section className="pf-card" aria-labelledby="pf-rc-h">
            <h2 id="pf-rc-h" className="pf-k">
              How we reach you
            </h2>
            {REACH.map((r) => (
              <SettingSwitch
                key={r.key}
                title={r.title}
                line={r.line}
                on={r.key === "teams" && !teamsOn ? false : settings[r.key]}
                disabled={r.key === "teams" && !teamsOn}
                soon={r.key === "teams" && !teamsOn}
                error={errors[r.key] ?? null}
                onFlip={() => void flip(r.key)}
              />
            ))}
          </section>
          <ReferAsCard />
        </div>
      </div>
    </div>
  );
}
