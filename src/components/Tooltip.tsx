"use client";

import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Info } from "lucide-react";

const TIP_W = 248;
const GAP = 8; // between trigger and tooltip
const MARGIN = 8; // minimum distance from viewport edges

/**
 * Info-dot tooltip: every technical term gets one. Works on hover, keyboard
 * focus, and touch (tap toggles). Never the only place a value lives.
 *
 * The bubble renders in a portal to <body> with fixed positioning, so it can
 * never be clipped by an ancestor's overflow (e.g. the board's scroll
 * container). It prefers sitting above the trigger and flips below when
 * there's no room; horizontally it clamps to the viewport.
 */
export function InfoTip({
  label,
  children,
  trigger,
  triggerClassName,
}: {
  /** Accessible name, e.g. "What does confidence mean?" */
  label: string;
  children: ReactNode;
  /** Kept for API compatibility — the portal clamps to the viewport itself. */
  align?: "center" | "left" | "right";
  /** Custom trigger content (defaults to the info dot). */
  trigger?: ReactNode;
  /** Extra classes for the trigger button (e.g. when trigger is a custom mark). */
  triggerClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const btnRef = useRef<HTMLButtonElement>(null);
  const tipRef = useRef<HTMLSpanElement | null>(null);
  // Whether the tip was open when the current press started. A tap fires
  // focus (which opens) before click — resolving click against the pre-press
  // state keeps "tap to open, tap again to close" honest on touch.
  const pressWasOpen = useRef<boolean | null>(null);

  // Callback ref: position the bubble the moment it hits the DOM (no
  // setState-in-effect, no flash — it mounts hidden and is placed once
  // measured).
  const placeTip = useCallback((tip: HTMLSpanElement | null) => {
    tipRef.current = tip;
    const btn = btnRef.current;
    if (!tip || !btn) return;
    const r = btn.getBoundingClientRect();
    const vw = window.innerWidth;
    const width = Math.min(TIP_W, vw - MARGIN * 2);
    tip.style.width = `${width}px`;
    const h = tip.offsetHeight;
    const left = Math.min(Math.max(r.left + r.width / 2 - width / 2, MARGIN), vw - width - MARGIN);
    let top = r.top - GAP - h;
    if (top < MARGIN) top = r.bottom + GAP; // flip below the trigger
    tip.style.top = `${top}px`;
    tip.style.left = `${left}px`;
    tip.style.visibility = "visible";
  }, []);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (btnRef.current?.contains(t) || tipRef.current?.contains(t)) return;
      close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    // Fixed positioning goes stale the moment anything scrolls — just close.
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span
      className="relative inline-flex align-middle"
      // Hover only for real mice — on touch, the synthesized mouseenter would
      // open the tip an instant before the tap's click toggled it shut again.
      onPointerEnter={(e) => {
        if (e.pointerType === "mouse") setOpen(true);
      }}
      onPointerLeave={(e) => {
        if (e.pointerType === "mouse") setOpen(false);
      }}
    >
      <button
        ref={btnRef}
        type="button"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onPointerDown={() => {
          pressWasOpen.current = open;
        }}
        onClick={() => {
          const wasOpen = pressWasOpen.current;
          pressWasOpen.current = null;
          setOpen(wasOpen === null ? (v) => !v : !wasOpen);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className={
          triggerClassName ??
          "inline-flex h-4 w-4 items-center justify-center rounded-full text-ink3 transition-colors hover:text-accent2"
        }
      >
        {trigger ?? <Info className="h-3.5 w-3.5" aria-hidden />}
      </button>
      {open &&
        typeof document !== "undefined" &&
        createPortal(
          <span
            ref={placeTip}
            id={id}
            role="tooltip"
            style={{ position: "fixed", top: 0, left: 0, width: TIP_W, visibility: "hidden" }}
            className="z-[80] rounded-lg border border-edge bg-raised px-3 py-2 text-left text-xs leading-relaxed font-normal tracking-normal normal-case text-ink2 shadow-xl shadow-black/50"
          >
            {children}
          </span>,
          document.body
        )}
    </span>
  );
}
