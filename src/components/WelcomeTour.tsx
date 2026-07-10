"use client";

import { useEffect, useState } from "react";
import { ChartSpline, Eye, MousePointerClick, X } from "lucide-react";
import { useTourSeen } from "../lib/store";
import { ResultsToggleName } from "./ui";

const BEATS = [
  {
    icon: ChartSpline,
    title: "Numbers are projections",
    body: "Every number here is a projection with a range around it — a best estimate, never a promise.",
  },
  {
    icon: MousePointerClick,
    title: "Tap for the why",
    body: "Tap any player and we explain the call in plain English — matchup, form, weather.",
  },
  {
    icon: Eye,
    title: "Check our receipts",
    body: null, // rendered inline — it references the header toggle by its visible name
  },
];

/**
 * First-visit orientation banner: three beats, dismissable, never a modal.
 * A localStorage flag keeps it gone after dismissal; the entrance animation
 * is the global fade-up, which prefers-reduced-motion already disables.
 */
export function WelcomeTour() {
  const [seen, dismiss] = useTourSeen();
  // Render nothing until after hydration so returning visitors never see a
  // flash. Deferred a tick (matching RevealContext) so the update never
  // cascades into the first render.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setMounted(true), 0);
    return () => window.clearTimeout(t);
  }, []);
  if (!mounted || seen) return null;

  return (
    <section
      role="region"
      aria-label="First-visit orientation"
      className="card fade-up relative mt-6 overflow-hidden border-accent/25 p-4 sm:p-5"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          background:
            "radial-gradient(480px 160px at 8% 0%, rgba(99,102,241,0.16), transparent 60%)",
        }}
      />
      <div className="relative">
        <div className="flex items-start justify-between gap-3">
          <p className="text-[11px] font-bold tracking-wider text-accent uppercase">
            New here? Three things in ten seconds
          </p>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Dismiss this orientation — it won't show again"
            className="-mt-1 -mr-1 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink3 transition-colors hover:bg-white/8 hover:text-ink"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <ol className="mt-3 grid gap-3 sm:grid-cols-3 sm:gap-5">
          {BEATS.map((b, i) => (
            <li key={b.title} className="flex items-start gap-2.5">
              <span className="accent-gradient mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md shadow-md shadow-accentdeep/25">
                <b.icon className="h-3.5 w-3.5 text-white" aria-hidden />
              </span>
              <span className="min-w-0 text-xs leading-relaxed text-ink2">
                <span className="block font-bold text-ink">
                  {i + 1}. {b.title}
                </span>
                {b.body ?? (
                  <>
                    Flip <ResultsToggleName /> in the header any time — this is a replayed week, so
                    every call can be checked against what really happened.
                  </>
                )}
              </span>
            </li>
          ))}
        </ol>
        <div className="mt-3.5 flex items-center gap-3">
          <button
            type="button"
            onClick={dismiss}
            className="accent-gradient inline-flex h-8 items-center rounded-full px-4 text-xs font-semibold text-white shadow-md shadow-accentdeep/25 transition-all hover:brightness-110"
          >
            Got it
          </button>
          <span className="text-[11px] text-ink3">Dismiss once and it stays gone.</span>
        </div>
      </div>
    </section>
  );
}
