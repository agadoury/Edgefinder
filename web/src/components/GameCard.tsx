import { CloudSun, Landmark, Wind } from "lucide-react";
import type { Game } from "../lib/data";
import { fmtKickoff, fmtLine, fmtSpread } from "../lib/format";
import { monogramInk, team } from "../lib/teams";

function TeamDot({ code }: { code: string }) {
  const t = team(code);
  return (
    <span
      aria-hidden
      className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
      style={{
        background: `linear-gradient(145deg, ${t.primary}, ${t.primary}dd)`,
        color: monogramInk(t.primary),
        boxShadow: `inset 0 0 0 2px ${t.secondary}55, 0 0 0 1px rgba(255,255,255,0.10)`,
      }}
    >
      {code}
    </span>
  );
}

export function WeatherChip({ game }: { game: Game }) {
  if (game.roof === "dome" || game.roof === "closed") {
    return (
      <span className="chip">
        <Landmark className="h-3 w-3 text-accent2" aria-hidden />
        Dome · indoors
      </span>
    );
  }
  const windy = (game.windMph ?? 0) >= 15;
  return (
    <span className={`chip ${windy ? "border-push/40 text-push" : ""}`}>
      {windy ? (
        <Wind className="h-3 w-3" aria-hidden />
      ) : (
        <CloudSun className="h-3 w-3 text-accent2" aria-hidden />
      )}
      {game.tempF !== null ? `${game.tempF}°F` : "—"}
      {game.windMph !== null ? ` · ${game.windMph} mph wind` : ""}
    </span>
  );
}

export function GameCard({ game }: { game: Game }) {
  return (
    <article className="card card-hover p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-ink3">{fmtKickoff(game.kickoff)}</span>
        <WeatherChip game={game} />
      </div>
      <div className="mt-3 flex items-center gap-3">
        <TeamDot code={game.away} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">
            {team(game.away).name} <span className="mx-0.5 font-normal text-ink3">at</span>{" "}
            {team(game.home).name}
          </p>
          <p className="truncate text-xs text-ink3">
            {game.awayQb} vs {game.homeQb}
          </p>
        </div>
        <TeamDot code={game.home} />
      </div>
      <div className="mt-3 flex items-center gap-2 border-t border-white/6 pt-3">
        <span className="chip tnum">O/U {fmtLine(game.vegasTotal)}</span>
        <span className="chip tnum">{fmtSpread(game)}</span>
        <span className="ml-auto min-w-0 truncate text-[11px] text-ink3">{game.stadium}</span>
      </div>
    </article>
  );
}
