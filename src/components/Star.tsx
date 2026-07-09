"use client";

import { Star } from "lucide-react";
import { useWatchlist } from "../lib/store";

/**
 * Watchlist star. Lives inside clickable rows/links, so it swallows the click
 * itself — starring never navigates. State persists in this browser only.
 */
export function StarButton({
  playerId,
  name,
  size = 16,
  className = "",
}: {
  playerId: string;
  name: string;
  size?: number;
  className?: string;
}) {
  const { has, toggle } = useWatchlist();
  const starred = has(playerId);
  return (
    <button
      type="button"
      aria-pressed={starred}
      aria-label={starred ? `Remove ${name} from my players` : `Add ${name} to my players`}
      title={starred ? "In my players — tap to remove" : "Star to add to my players"}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        toggle(playerId);
      }}
      className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-white/6 ${
        starred ? "text-push" : "text-ink3 hover:text-ink"
      } ${className}`}
    >
      <Star
        style={{ width: size, height: size }}
        aria-hidden
        fill={starred ? "currentColor" : "none"}
        strokeWidth={2}
      />
    </button>
  );
}
