import Link from "next/link";
import { ArrowRight, SearchX, X } from "lucide-react";

/** Branded 404 — renders inside the root layout, so header/footer stay. */
export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col items-center px-4 pt-20 pb-16 text-center sm:px-6 sm:pt-28">
      {/* a graded miss, because that's what this page is */}
      <div className="card flex items-center gap-3 border-white/10 px-5 py-3">
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-under/15 text-under">
          <X className="h-4.5 w-4.5" strokeWidth={3.2} aria-hidden />
        </span>
        <span className="text-left">
          <span className="block text-[10px] font-bold tracking-wider text-ink3 uppercase">
            Our call: this page exists
          </span>
          <span className="tnum block text-sm font-bold text-under">404 · MISS</span>
        </span>
      </div>

      <h1 className="mt-8 text-4xl font-bold tracking-tight sm:text-5xl">
        That one isn&apos;t on the board.
      </h1>
      <p className="mt-4 max-w-md text-base leading-relaxed text-ink2">
        The page you&apos;re after doesn&apos;t exist — the link may have rotted, or the player
        isn&apos;t on this week&apos;s slate. Either way, we take the L and show you the way back.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/#board"
          className="accent-gradient inline-flex h-11 items-center gap-2 rounded-full px-6 text-sm font-semibold text-white shadow-lg shadow-accentdeep/30 transition-all hover:brightness-110"
        >
          This week&apos;s calls
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
        <Link
          href="/how-it-works"
          className="inline-flex h-11 items-center rounded-full border border-white/12 bg-white/4 px-6 text-sm font-semibold text-ink2 transition-colors hover:border-white/25 hover:text-ink"
        >
          How it works
        </Link>
      </div>

      <p className="mt-10 flex items-center gap-1.5 text-xs text-ink3">
        <SearchX className="h-3.5 w-3.5" aria-hidden />
        Player pages follow the slate — links from older weeks can retire.
      </p>
    </div>
  );
}
