"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Eye, EyeOff, Zap } from "lucide-react";
import { useReveal } from "./RevealContext";
import { PickemHeaderChip } from "./Pickem";

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
  return (
    <Link
      href={href}
      className={`rounded-full px-2 py-1.5 text-xs font-medium whitespace-nowrap transition-colors sm:px-3 sm:text-sm ${
        active ? "bg-white/8 text-ink" : "text-ink2 hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}

export function Header({ season, week }: { season: number; week: number }) {
  const { revealed, toggle } = useReveal();
  return (
    <header className="sticky top-0 z-50 border-b border-white/7 bg-canvas/95 backdrop-blur-xl sm:bg-canvas/80">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-1.5 px-3 sm:h-16 sm:gap-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 sm:gap-2.5" aria-label="EdgeFinder home">
          <span className="accent-gradient inline-flex h-7 w-7 items-center justify-center rounded-lg shadow-lg shadow-accentdeep/30 sm:h-8 sm:w-8">
            <Zap className="h-4 w-4 text-white sm:h-4.5 sm:w-4.5" aria-hidden strokeWidth={2.5} fill="currentColor" />
          </span>
          <span className="flex flex-col">
            <span className="text-[15px] leading-tight font-bold tracking-tight sm:text-[17px]">
              Edge<span className="accent-text">Finder</span>
            </span>
            {/* compact replay cue — the sm+ chip below doesn't fit here */}
            <span
              className="flex items-center gap-1 text-[9px] leading-tight font-semibold tracking-wider text-ink3 uppercase sm:hidden"
              title="You are replaying a completed week"
            >
              <span className="h-1 w-1 rounded-full bg-accent2" aria-hidden />
              Wk {week} replay
            </span>
          </span>
        </Link>
        <span className="chip hidden sm:inline-flex" title="You are replaying a completed week">
          <span className="h-1.5 w-1.5 rounded-full bg-accent2" aria-hidden />
          Replay · {season} Wk {week}
        </span>
        <PickemHeaderChip />

        <nav className="ml-auto flex items-center gap-0.5 sm:gap-1" aria-label="Main">
          <NavLink href="/">This week</NavLink>
          <NavLink href="/how-it-works">How it works</NavLink>
        </nav>

        <button
          type="button"
          role="switch"
          aria-checked={revealed}
          onClick={toggle}
          className={`ml-1 inline-flex h-9 items-center gap-1.5 rounded-full border px-2.5 text-xs font-semibold transition-all sm:ml-2 sm:gap-2 sm:px-3 sm:text-sm ${
            revealed
              ? "border-over/40 bg-over/10 text-over"
              : "border-white/12 bg-white/4 text-ink2 hover:border-white/25 hover:text-ink"
          }`}
        >
          {revealed ? (
            <Eye className="h-4 w-4" aria-hidden />
          ) : (
            <EyeOff className="h-4 w-4" aria-hidden />
          )}
          <span className="sm:hidden">Results</span>
          <span className="hidden sm:inline">Show results</span>
          <span
            aria-hidden
            className={`relative hidden h-4 w-7 rounded-full transition-colors sm:inline-block ${
              revealed ? "bg-over/60" : "bg-white/15"
            }`}
          >
            <span
              className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-transform ${
                revealed ? "translate-x-3.5" : "translate-x-0.5"
              }`}
            />
          </span>
        </button>
      </div>
    </header>
  );
}
