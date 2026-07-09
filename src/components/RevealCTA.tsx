"use client";

import { Eye, EyeOff } from "lucide-react";
import { useReveal } from "./RevealContext";

/** Inline "show the receipts" button used in the replay banner. */
export function RevealCTA() {
  const { revealed, toggle } = useReveal();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={revealed}
      className={`inline-flex h-9 shrink-0 items-center gap-2 rounded-full px-4 text-sm font-semibold transition-all ${
        revealed
          ? "border border-over/40 bg-over/10 text-over"
          : "accent-gradient text-white shadow-lg shadow-accentdeep/30 hover:brightness-110"
      }`}
    >
      {revealed ? <Eye className="h-4 w-4" aria-hidden /> : <EyeOff className="h-4 w-4" aria-hidden />}
      {revealed ? "Results are showing" : "Show the receipts"}
    </button>
  );
}
