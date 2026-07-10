// "Where to next" strip for player pages — pure presentation, server-safe.
// Un-dead-ends the player page: teammates & opponents from the same game,
// plus the next call by global strength order.
import Link from "next/link";
import { ArrowRight, ArrowDown, ArrowUp, Minus } from "lucide-react";
import type { Lean, SlateProp } from "../lib/data";
import { MARKET_SHORT } from "../lib/format";
import { strengthTier } from "../lib/tiers";
import { PlayerAvatar } from "./PlayerAvatar";
import { InfoTip } from "./Tooltip";

function LeanMini({ lean }: { lean: Lean }) {
  const Icon = lean === "over" ? ArrowUp : lean === "under" ? ArrowDown : Minus;
  const cls = lean === "over" ? "text-over" : lean === "under" ? "text-under" : "text-ink3";
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-bold ${cls}`}>
      <Icon className="h-3 w-3" strokeWidth={3} aria-hidden />
      {lean === "over" ? "OVER" : lean === "under" ? "UNDER" : "NO LEAN"}
    </span>
  );
}

export function NextUp({
  gameLabel,
  sameGame,
  nextCall,
  headshots = {},
}: {
  /** e.g. "CIN @ BUF" */
  gameLabel: string;
  /** Best call per other player in this game, strongest first. */
  sameGame: SlateProp[];
  /** The next player-market by global strength order (different player). */
  nextCall: SlateProp | null;
  headshots?: Record<string, string>;
}) {
  if (sameGame.length === 0 && !nextCall) return null;
  return (
    <section className="card p-5 sm:p-6" aria-label="Keep browsing">
      {sameGame.length > 0 && (
        <>
          <h3 className="flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-ink3 uppercase">
            More from {gameLabel}
            <InfoTip label="What is this list?">
              Every other player we cover in this same game, strongest call first — so you can read
              the whole matchup without going back to the board.
            </InfoTip>
          </h3>
          <ul className="mt-3 flex flex-wrap gap-2">
            {sameGame.map((r) => (
              <li key={r.playerId}>
                <Link
                  href={`/players/${r.playerId}`}
                  className="group flex items-center gap-2 rounded-full border border-white/8 bg-white/3 py-1.5 pr-3.5 pl-1.5 transition-colors hover:border-accent/40 hover:bg-white/6"
                >
                  <PlayerAvatar
                    name={r.name}
                    teamCode={r.team}
                    size={26}
                    src={headshots[r.playerId]}
                  />
                  <span className="text-xs leading-tight">
                    <span className="block font-semibold text-ink group-hover:text-accent">
                      {r.name}
                    </span>
                    <span className="flex items-center gap-1.5 text-[10px] text-ink3">
                      {MARKET_SHORT[r.market]} <LeanMini lean={r.lean} />
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}

      {nextCall && (
        <div className={sameGame.length > 0 ? "mt-5 border-t border-white/6 pt-4" : ""}>
          <Link
            href={`/players/${nextCall.playerId}`}
            className="group flex flex-wrap items-center gap-x-3 gap-y-1.5"
          >
            <span className="text-[11px] font-bold tracking-wider text-ink3 uppercase">
              Next top call
            </span>
            <span className="flex items-center gap-2">
              <PlayerAvatar
                name={nextCall.name}
                teamCode={nextCall.team}
                size={26}
                src={headshots[nextCall.playerId]}
              />
              <span className="text-sm font-semibold text-ink group-hover:text-accent group-hover:underline group-hover:decoration-accent/40 group-hover:underline-offset-4">
                {nextCall.name}
              </span>
              <span className="text-xs text-ink3">
                {MARKET_SHORT[nextCall.market]} · {strengthTier(nextCall.strength).label} ·{" "}
                <span className="tnum">{nextCall.strength}</span>
              </span>
              <LeanMini lean={nextCall.lean} />
            </span>
            <ArrowRight
              className="h-4 w-4 text-accent2 transition-transform group-hover:translate-x-0.5"
              aria-hidden
            />
          </Link>
        </div>
      )}
    </section>
  );
}
