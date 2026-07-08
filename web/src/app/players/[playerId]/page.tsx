import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, CalendarDays, MapPin } from "lucide-react";
import {
  getGame,
  getHeadshots,
  getMarketMeta,
  getMeta,
  getPlayer,
  getPlayerIds,
} from "../../../lib/data";
import { fmtKickoff, fmtLine, fmtSpread, firstName } from "../../../lib/format";
import { teamFullName } from "../../../lib/teams";
import { PlayerAvatar } from "../../../components/PlayerAvatar";
import { WeatherChip } from "../../../components/GameCard";
import { MarketCard } from "../../../components/MarketCard";
import { Receipts } from "../../../components/Receipts";
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
          src={getHeadshots()[player.playerId]}
        />
        <div className="min-w-0 flex-1">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{player.name}</h1>
          <p className="mt-1 text-sm text-ink2">
            {player.pos} · {teamFullName(player.team)}{" "}
            <span className="text-ink3">
              {matchupWord} {teamFullName(player.opponent)} · {player.gamesPlayed2025} games this
              season
            </span>
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
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
          </div>
        </div>
      </header>

      {/* ---------- market cards ---------- */}
      <div className="mt-8 grid gap-6">
        {player.props.map((prop) => (
          <MarketCard
            key={prop.market}
            prop={prop}
            market={getMarketMeta(prop.market)}
            first={first}
            recentGames={player.recentGames}
          />
        ))}

        <Receipts history={player.modelHistory} first={first} />
      </div>

      <p className="mt-8 text-xs leading-relaxed text-ink3">
        Replay of {meta.season} Week {meta.week}. Projections are estimates, not guarantees —
        reference lines are EdgeFinder&apos;s own, not sportsbook lines.
      </p>
    </div>
  );
}
