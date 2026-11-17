"use client";

/**
 * S-R2 "Hide this" (L-HIDE.rules/7, NOT DRAWN; default: reviewers can flag text, which masks it at once and notifies
 * the sharer). BLD-B246.
 *
 * - Each text that is one stored source (the title, a part kept as one text, an answer, one of the sharer's messages)
 *   is a `Hideable`. When the reviewer selects words inside one, "Hide this" shows just under the end of the
 *   selection. It sits in the page right after that text, so from a keyboard selection (caret browsing: F7, then
 *   Shift and the arrow keys) Tab reaches it next; Escape closes it and gives focus back to the text.
 * - It posts the selection's UTF-16 offsets to lane C's route, which masks every copy and tells the sharer. On 200
 *   the page is read again, so every copy shows masked; a refusal shows in plain words under the button.
 */
import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { Button } from "@/components/ui/button";
import {
  HIDDEN_DONE,
  HIDE_THIS,
  hideBody,
  hideErrorWords,
  hideUrl,
  rangeOffsets,
  type HideSource,
  type HideSourceKind,
} from "@/lib/desk/hide";
import { call } from "@/lib/desk/reply";

interface Picked {
  key: string;
  ideaId: string;
  source: HideSource;
  start: number;
  end: number;
}

interface HideState {
  picked: Picked | null;
  error: string | null;
  hide: () => void;
  close: () => void;
}

const HideContext = createContext<HideState | null>(null);

function hostOf(node: Node | null): HTMLElement | null {
  const el = node instanceof HTMLElement ? node : (node?.parentElement ?? null);
  return el?.closest<HTMLElement>("[data-hide-key]") ?? null;
}

function hostByKey(key: string): HTMLElement | null {
  for (const el of document.querySelectorAll<HTMLElement>("[data-hide-key]")) {
    if (el.dataset.hideKey === key) return el;
  }
  return null;
}

/** Offers "Hide this" on the page's texts when `enabled` (the review desk and the Ones Committee, not on their own idea). */
export function HideThisProvider({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const router = useRouter();
  const [picked, setPicked] = useState<Picked | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState("");
  const busy = useRef(false);
  const current = useRef<Picked | null>(null);
  useEffect(() => {
    current.current = picked;
  }, [picked]);

  useEffect(() => {
    if (!enabled) return;
    const onChange = () => {
      if (busy.current) return;
      // focus on "Hide this" itself (Tab from a keyboard selection) keeps the selection it was offered for
      const active = document.activeElement;
      if (active instanceof HTMLElement && active.closest("[data-hide-ui]")) return;
      const sel = document.getSelection();
      const range = sel && sel.rangeCount > 0 && !sel.isCollapsed ? sel.getRangeAt(0) : null;
      const host = range ? hostOf(range.startContainer) : null;
      const at = range && host && hostOf(range.endContainer) === host ? rangeOffsets(host, range) : null;
      const prev = current.current;
      if (!range || !host || !at) {
        if (prev) {
          setPicked(null);
          setError(null);
        }
        return;
      }
      const d = host.dataset;
      if (prev && prev.key === d.hideKey && prev.start === at.start && prev.end === at.end) return;
      setPicked({
        key: d.hideKey ?? "",
        ideaId: d.hideIdea ?? "",
        source: { kind: (d.hideKind ?? "") as HideSourceKind, id: d.hideId ?? "" },
        ...at,
      });
      setError(null);
      setDone("");
    };
    document.addEventListener("selectionchange", onChange);
    return () => document.removeEventListener("selectionchange", onChange);
  }, [enabled]);

  const close = useCallback(() => {
    if (!picked) return;
    const host = hostByKey(picked.key);
    setPicked(null);
    setError(null);
    document.getSelection()?.removeAllRanges();
    host?.focus({ preventScroll: true });
  }, [picked]);

  const hide = useCallback(() => {
    if (!picked || busy.current) return;
    busy.current = true;
    setError(null);
    void call<unknown>(hideUrl(picked.ideaId), {
      method: "POST",
      body: hideBody(picked.source, picked),
    }).then((res) => {
      busy.current = false;
      if (!res.ok) {
        setError(hideErrorWords(res.error.code));
        return;
      }
      const host = hostByKey(picked.key);
      setPicked(null);
      document.getSelection()?.removeAllRanges();
      host?.focus({ preventScroll: true });
      setDone(HIDDEN_DONE);
      router.refresh(); // every copy reads masked now (lane C masks them all at once)
    });
  }, [picked, router]);

  const value = useMemo<HideState | null>(
    () => (enabled ? { picked, error, hide, close } : null),
    [enabled, picked, error, hide, close],
  );
  return (
    <HideContext.Provider value={value}>
      {children}
      <p className="visually-hidden" role="status">
        {done}
      </p>
    </HideContext.Provider>
  );
}

type TextTag = "p" | "h1" | "span";

/** One text the reviewer may hide words in: `text` must be exactly the stored text of `source` on idea `ideaId`. */
export function Hideable({
  as: Tag = "p",
  className,
  ideaId,
  source,
  text,
}: {
  as?: TextTag;
  className?: string;
  ideaId: string;
  source: HideSource | null;
  text: string;
}) {
  const ctx = useContext(HideContext);
  if (!ctx || !source) return <Tag className={className}>{text}</Tag>;
  const key = `${ideaId}|${source.kind}|${source.id}`;
  return (
    <>
      <Tag
        className={className}
        data-hide-key={key}
        data-hide-idea={ideaId}
        data-hide-kind={source.kind}
        data-hide-id={source.id}
        tabIndex={-1}
      >
        {text}
      </Tag>
      {ctx.picked?.key === key ? <HideButton state={ctx} /> : null}
    </>
  );
}

/** Out of the flow, just under the end of the selection, clamped to its container. */
function HideButton({ state }: { state: HideState }) {
  const box = useRef<HTMLSpanElement>(null);
  const { picked, error, hide, close } = state;
  useLayoutEffect(() => {
    const el = box.current;
    const sel = document.getSelection();
    if (!el || !sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    const rects = range.getClientRects();
    const last = rects.length ? rects[rects.length - 1]! : range.getBoundingClientRect();
    const parent = (el.offsetParent as HTMLElement | null) ?? document.documentElement;
    const p = parent.getBoundingClientRect();
    const left = Math.max(0, Math.min(last.left - p.left, parent.clientWidth - el.offsetWidth));
    el.style.left = `${left}px`;
    el.style.top = `${last.bottom - p.top + parent.scrollTop + 6}px`;
    el.dataset.placed = "";
  }, [picked]);
  return (
    <span ref={box} className="ri-hide" data-hide-ui="">
      <Button
        variant="line"
        size="sm"
        onMouseDown={(e) => e.preventDefault()} // keep the selection while the pointer presses it
        onClick={hide}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            close();
          }
        }}
      >
        {HIDE_THIS}
      </Button>
      {error ? (
        <span className="meta ri-hide-err" role="alert">
          {error}
        </span>
      ) : null}
    </span>
  );
}
