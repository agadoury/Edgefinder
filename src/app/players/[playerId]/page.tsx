import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight, CalendarDays, MapPin } from "lucide-react";
import {
  getGame,
  getHeadshots,
  getMarketMeta,
  getMeta,
  getPlayer,
  getPlayerIds,
  getSlate,
  type SlateProp,
} from "../../../lib/data";
import { AVAILABILITY_WINDOW, getAvailabilityWatch } from "../../../lib/availability";
import { fmtKickoff, fmtLine, fmtSpread, firstName } from "../../../lib/format";
import { teamFullName } from "../../../lib/teams";
import { PlayerAvatar } from "../../../components/PlayerAvatar";
import { WeatherChip } from "../../../components/GameCard";
import { MarketCard } from "../../../components/MarketCard";
import { NextUp } from "../../../components/NextUp";
import { Receipts } from "../../../components/Receipts";
import { StarButton } from "../../../components/Star";
import { PickemPanel } from "../../../components/Pickem";
import { InfoTip } from "../../../components/Tooltip";

export function generateStaticParams() {
  return getPlayerIds().map((playerId) => ({ playerId }));
}

export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ playerId: string }>;
}) {
  const { playerId } = await params;
  try {
    const player = getPlayer(playerId);
    return {
      title: `${player.name} — EdgeFinder projections`,
      description: `AI projections for ${player.name} (${player.pos}, ${player.team}) vs ${player.opponent}, explained in plain English.`,
    };
  } catch {
    return { title: "Player — EdgeFinder" };
  }
}

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ playerId: string }>;
}) {
  const { playerId } = await params;
  let player;
  try {
    player = getPlayer(playerId);
  } catch {
    notFound();
  }
  const meta = getMeta();
  const game = getGame(player.gameId);
  const first = firstName(player.name);
  const matchupWord = player.home ? "vs" : "at";
  const headshots = getHeadshots();
  const missedWeeks = getAvailabilityWatch()[player.playerId];

  // ----- next-step flow: same-game players + the next call by strength -----
  const slate = getSlate();
  const bestByPlayer = new Map<string, SlateProp>();
  for (const r of slate.props) {
    if (r.gameId !== player.gameId || r.playerId === player.playerId) continue;
    const cur = bestByPlayer.get(r.playerId);
    if (!cur || r.strength > cur.strength) bestByPlayer.set(r.playerId, r);
  }
  const sameGame = [...bestByPlayer.values()]
    .sort((a, b) => b.strength - a.strength || a.name.localeCompare(b.name))
    .slice(0, 8);

  const ordered = [...slate.props].sort(
    (a, b) =>
      b.strength - a.strength ||
      a.name.localeCompare(b.name) ||
      a.market.localeCompare(b.market)
  );
  const idx = ordered.findIndex((r) => r.playerId === player.playerId);
  let nextCall: SlateProp | null = null;
  for (let i = 1; i <= ordered.length && idx !== -1; i++) {
    const candidate = ordered[(idx + i) % ordered.length];
    if (candidate.playerId !== player.playerId) {
      nextCall = candidate;
      break;
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 pt-8 sm:px-6">
      <Link
        href="/#board"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink3 transition-colors hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to this week&apos;s calls
      </Link>

      {/* ---------- player header ---------- */}
      <header className="mt-6 flex flex-col gap-5 sm:flex-row sm:items-center">
        <PlayerAvatar
          name={player.name}
          teamCode={player.team}
          size={72}
          src={headshots[player.playerId]}
        />
        <div className="min-w-0 flex-1">
          <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight sm:text-4xl">
            {player.name}
            <StarButton playerId={player.playerId} name={player.name} size={20} className="mt-1" />
          </h1>
          <p className="mt-1 text-sm text-ink2">
            {player.pos} · {teamFullName(player.team)}{" "}
            <span className="text-ink3">
              {matchupWord} {teamFullName(player.opponent)} · {player.gamesPlayed2025} games this
              season
            </span>
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Link
              href={`/games/${player.gameId}`}
              className="chip font-semibold transition-colors hover:border-accent/40 hover:text-ink"
              aria-label={`All calls for ${game.away} at ${game.home}`}
            >
              {game.away} @ {game.home} · game hub
              <ArrowRight className="h-3 w-3 text-accent2" aria-hidden />
            </Link>
            <span className="chip">
              <CalendarDays className="h-3 w-3 text-accent2" aria-hidden />
              {fmtKickoff(game.kickoff)}
            </span>
            <span className="chip">
              <MapPin className="h-3 w-3 text-accent2" aria-hidden />
              {game.stadium}
            </span>
            <WeatherChip game={game} />
            <span className="chip tnum">
              O/U {fmtLine(game.vegasTotal)}
              <InfoTip label="What is the game total?">
                Vegas&apos;s expected combined score for this game. Higher totals usually mean more
                yards to go around.
              </InfoTip>
            </span>
            <span className="chip tnum">
              {fmtSpread(game)}
              <InfoTip label="What is the spread?">
                Who Vegas favors and by how much. Close spreads keep game plans balanced; big ones
                can change how teams play late.
              </InfoTip>
            </span>
            {missedWeeks && (
              <span className="chip border-push/30 bg-push/8 font-semibold text-push">
                <span
                  className="h-1.5 w-1.5 rounded-full bg-push shadow-[0_0_6px_rgba(251,191,36,0.55)]"
                  aria-hidden
                />
                Availability watch
                <InfoTip label={`Availability watch for ${player.name}`}>
                  {first} sat out{" "}
                  {missedWeeks.length === 1
                    ? `week ${missedWeeks[0]}`
                    : `weeks ${missedWeeks.join(", ")}`}{" "}
                  — {missedWeeks.length} of the {AVAILABILITY_WINDOW}{" "}
                  weeks before this one, while his team played. A schedule fact from before
                  kickoff, not a spoiler of this week&apos;s result.
                </InfoTip>
              </span>
            )}
          </div>
        </div>
      </header>

      {/* ---------- pick 'em ---------- */}
      <div className="mt-8">
        <PickemPanel />
      </div>

      {/* ---------- market cards ---------- */}
      <div className="mt-6 grid gap-6">
        {player.props.map((prop) => (
          <MarketCard
            key={prop.market}
            prop={prop}
            market={getMarketMeta(prop.market)}
            first={first}
            playerId={player.playerId}
            recentGames={player.recentGames}
            coverage80={meta.backtest.byMarket[prop.market]?.coverage80 ?? null}
          />
        ))}

        <Receipts history={player.modelHistory} first={first} />

        {/* where to next — never a dead end */}
        <NextUp
          gameLabel={`${game.away} @ ${game.home}`}
          sameGame={sameGame}
          nextCall={nextCall}
          headshots={headshots}
        />
      </div>

      <p className="mt-8 text-xs leading-relaxed text-ink3">
        Replay of {meta.season} Week {meta.week}. Projections are estimates, not guarantees —
        reference lines are EdgeFinder&apos;s own, not sportsbook lines.
      </p>
    </div>
  );
}
