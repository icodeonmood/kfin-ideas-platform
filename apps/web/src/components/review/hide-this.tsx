"use client";

/**
 * S-R2 "Hide this" (L-HIDE.rules/7, NOT DRAWN; default: reviewers can flag text, which masks it at once and notifies
 * the sharer). BLD-B246.
 *
 * - Each text that is one stored source (the title, a part kept as one text, an answer, one of the sharer's messages)
 *   is a `Hideable`. When the reviewer selects words inside one, "Hide this" shows just under the end of the
 *   selection. It sits in the page right after that text, so Tab reaches it next; Escape closes it and gives focus
 *   back to the text.
 * - Keyboard (WCAG 2.1.1, 4.1.3; BLD-B247): each text is in the Tab order with a name ("The problem, text"); an
 *   arrow, Home or End moves the caret in it, Shift with them selects from the caret, Enter moves to "Hide this",
 *   and the status region says "Hide this is next. Press Tab." each time it appears (cleared when the selection
 *   ends). Caret browsing (F7) works as before.
 * - It is offered only while the text on the page is exactly the stored text it stands for (a CRLF the HTML parser
 *   turned into LF would shift every offset after it); otherwise "Select again." shows under the text.
 * - It posts the selection's UTF-16 offsets and the selected masked words to lane C's route, which masks every copy
 *   and tells the sharer. On 200 the page is read again, so every copy shows masked; a refusal shows in plain words
 *   under the button; `stale` (the text changed under the selection) reads the page again and says so.
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
  HIDE_NEXT,
  HIDE_THIS,
  HIDE_WORDS,
  caretStep,
  hideBody,
  hideErrorWords,
  hideUrl,
  opensHide,
  rangeOffsets,
  type CaretStep,
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
  selected: string;
}

interface HideState {
  picked: Picked | null;
  error: string | null;
  /** A line left under a text once its button has gone ("The page changed. Select again."). */
  notice: { key: string; text: string } | null;
  hide: () => void;
  close: () => void;
  /** Tells the provider the stored text a host stands for; returns the undo. */
  register: (key: string, text: string) => () => void;
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

const MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent);

/** An arrow, Home or End inside a focused text: the caret starts at the text's start (or, going back, its end) when
 * it is not in the text yet, then moves, or with Shift extends the selection, by `step`, and stays inside the text. */
function stepIn(host: HTMLElement, step: CaretStep) {
  const sel = document.getSelection();
  const first = host.firstChild;
  const last = host.lastChild;
  if (!sel || !first || !last) return;
  const lastLength = last.textContent?.length ?? 0;
  const inside = sel.rangeCount > 0 && host.contains(sel.anchorNode) && host.contains(sel.focusNode);
  if (!inside) {
    if (step.direction === "forward") sel.collapse(first, 0);
    else sel.collapse(last, lastLength);
  }
  sel.modify(step.alter, step.direction, step.granularity);
  if (host.contains(sel.focusNode)) return;
  if (step.alter === "move" || !sel.anchorNode) {
    if (step.direction === "forward") sel.collapse(last, lastLength);
    else sel.collapse(first, 0);
  } else if (step.direction === "forward") {
    sel.setBaseAndExtent(sel.anchorNode, sel.anchorOffset, last, lastLength);
  } else sel.setBaseAndExtent(sel.anchorNode, sel.anchorOffset, first, 0);
}

/** Offers "Hide this" on the page's texts when `enabled` (the review desk and the Ones Committee, not on their own idea). */
export function HideThisProvider({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const router = useRouter();
  const [picked, setPicked] = useState<Picked | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ key: string; text: string } | null>(null);
  const [done, setDone] = useState("");
  /** Says `line` in the status region even when it already holds it: emptied first, then set in a later step, so the
   * region changes and the screen reader reads it again (WCAG 4.1.3; BLD-B247). */
  const say = useCallback((line: string) => {
    setDone("");
    queueMicrotask(() => setDone(line));
  }, []);
  const busy = useRef(false);
  const current = useRef<Picked | null>(null);
  /** The text "Select again." was last said for, so it is said once per text and not on every key. */
  const lastNotice = useRef<string | null>(null);
  const texts = useRef(new Map<string, string>());
  const register = useCallback((key: string, text: string) => {
    texts.current.set(key, text);
    return () => {
      if (texts.current.get(key) === text) texts.current.delete(key);
    };
  }, []);
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
      const one = range !== null && host !== null && hostOf(range.endContainer) === host;
      // offered only while the page shows exactly the stored text, so the offsets are the stored text's
      const exact = host !== null && host.textContent === texts.current.get(host.dataset.hideKey ?? "");
      const at = range && host && one && exact ? rangeOffsets(host, range) : null;
      const prev = current.current;
      if (!range || !host || !at) {
        if (prev) {
          current.current = null;
          setPicked(null);
          setError(null);
          setDone(""); // the next "Hide this" is said again
        }
        if (!range) lastNotice.current = null;
        if (host && one && !exact) {
          // the page's text is not the stored text: say so rather than offer nothing (BLD-B247)
          const k = host.dataset.hideKey ?? "";
          if (lastNotice.current !== k) {
            lastNotice.current = k;
            setNotice({ key: k, text: HIDE_WORDS.select_again });
            say(HIDE_WORDS.select_again);
          }
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
      setNotice(null);
      lastNotice.current = null;
      if (!prev || prev.key !== d.hideKey) say(HIDE_NEXT); // said as it appears, not on every key
    };
    document.addEventListener("selectionchange", onChange);
    return () => document.removeEventListener("selectionchange", onChange);
  }, [enabled, say]);

  const close = useCallback(() => {
    if (!picked) return;
    const host = hostByKey(picked.key);
    current.current = null;
    setPicked(null);
    setError(null);
    setDone("");
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
      if (!res.ok && res.error.code === "stale") {
        // the text changed under the selection: read the page again and ask for a new selection (BLD-B247)
        current.current = null; // so the selection's end does not empty the line said here
        setPicked(null);
        document.getSelection()?.removeAllRanges();
        setNotice({ key: picked.key, text: HIDE_WORDS.stale });
        say(HIDE_WORDS.stale);
        hostByKey(picked.key)?.focus({ preventScroll: true });
        router.refresh();
        return;
      }
      if (!res.ok) {
        setError(hideErrorWords(res.error.code));
        return;
      }
      const host = hostByKey(picked.key);
      current.current = null; // so the selection's end does not empty the line said here
      setPicked(null);
      document.getSelection()?.removeAllRanges();
      host?.focus({ preventScroll: true });
      say(HIDDEN_DONE);
      router.refresh(); // every copy reads masked now (lane C masks them all at once)
    });
  }, [picked, router, say]);

  const value = useMemo<HideState | null>(
    () => (enabled ? { picked, error, notice, hide, close, register } : null),
    [enabled, picked, error, notice, hide, close, register],
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

/**
 * One text the reviewer may hide words in: `text` must be exactly the stored text of `source` on idea `ideaId`.
 * `name` is what a screen reader says when it takes focus ("The problem, text", `hideableName`); a heading keeps its
 * own words as its name.
 */
export function Hideable({
  as: Tag = "p",
  className,
  ideaId,
  name,
  source,
  text,
}: {
  as?: TextTag;
  className?: string;
  ideaId: string;
  name: string;
  source: HideSource | null;
  text: string;
}) {
  const ctx = useContext(HideContext);
  const key = source ? `${ideaId}|${source.kind}|${source.id}` : "";
  const register = ctx?.register;
  useEffect(() => (register && key ? register(key, text) : undefined), [register, key, text]);
  if (!ctx || !source) return <Tag className={className}>{text}</Tag>;
  const heading = Tag === "h1";
  return (
    <>
      <Tag
        className={className}
        data-hide-key={key}
        data-hide-idea={ideaId}
        data-hide-kind={source.kind}
        data-hide-id={source.id}
        tabIndex={0}
        {...(heading ? {} : { role: "group", "aria-label": name })}
        onKeyDown={(e) => {
          const step = caretStep(e, MAC);
          if (step) {
            e.preventDefault();
            stepIn(e.currentTarget, step);
            return;
          }
          if (opensHide(e) && ctx.picked?.key === key) {
            e.preventDefault();
            e.currentTarget.nextElementSibling?.querySelector<HTMLButtonElement>("button")?.focus();
          }
        }}
      >
        {text}
      </Tag>
      {ctx.picked?.key === key ? (
        <HideButton state={ctx} />
      ) : ctx.notice?.key === key ? (
        <span className="meta ri-hide-note">{ctx.notice.text}</span>
      ) : null}
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
