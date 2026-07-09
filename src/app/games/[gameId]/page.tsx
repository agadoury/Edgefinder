import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, CalendarDays, MapPin } from "lucide-react";
import { getHeadshots, getMeta, getSlate } from "../../../lib/data";
import { fmtKickoff, fmtLine, fmtSpread } from "../../../lib/format";
import { team, teamFullName } from "../../../lib/teams";
import { Board } from "../../../components/Board";
import { TeamDot, WeatherChip } from "../../../components/GameCard";
import { InfoTip } from "../../../components/Tooltip";

export function generateStaticParams() {
  return getSlate().games.map((g) => ({ gameId: g.gameId }));
}

export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ gameId: string }>;
}) {
  const { gameId } = await params;
  const game = getSlate().games.find((g) => g.gameId === gameId);
  if (!game) return { title: "Game — EdgeFinder" };
  return {
    title: `${teamFullName(game.away)} at ${teamFullName(game.home)} — EdgeFinder game hub`,
    description: `Every EdgeFinder call for ${game.away} @ ${game.home}: projections, leans, and the full plain-English breakdowns.`,
  };
}

export default async function GamePage({
  params,
}: {
  params: Promise<{ gameId: string }>;
}) {
  const { gameId } = await params;
  const slate = getSlate();
  const game = slate.games.find((g) => g.gameId === gameId);
  if (!game) notFound();
  const meta = getMeta();
  const rows = slate.props.filter((p) => p.gameId === gameId);

  return (
    <div className="mx-auto max-w-6xl px-4 pt-8 sm:px-6">
      <Link
        href="/#board"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-ink3 transition-colors hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to the full Week {meta.week} slate
      </Link>

      {/* ---------- game header ---------- */}
      <header className="mt-6">
        <div className="flex flex-wrap items-center gap-4">
          <span className="flex items-center -space-x-2" aria-hidden>
            <TeamDot code={game.away} size={56} />
            <TeamDot code={game.home} size={56} />
          </span>
          <div className="min-w-0">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              {teamFullName(game.away)}{" "}
              <span className="font-normal text-ink3">at</span>{" "}
              {teamFullName(game.home)}
            </h1>
            <p className="mt-1 text-sm text-ink2">
              {game.awayQb} vs {game.homeQb}
              <span className="text-ink3">
                {" "}
                · Week {meta.week} · {rows.length} calls in this game
              </span>
            </p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
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
      </header>

      {/* ---------- this game's calls ---------- */}
      <section className="mt-10 scroll-mt-24">
        <h2 className="text-2xl font-bold tracking-tight">
          Every call for {game.away} @ {game.home}
        </h2>
        <p className="mt-1 mb-5 max-w-2xl text-sm text-ink2">
          Filter by team with the{" "}
          <span className="font-medium text-ink">
            {team(game.away).name}/{team(game.home).name}
          </span>{" "}
          pills — or click any row for the full story.
        </p>
        <Board
          rows={rows}
          games={[game]}
          markets={meta.markets}
          headshots={getHeadshots()}
        />
      </section>

      <p className="mt-8 text-xs leading-relaxed text-ink3">
        Replay of {meta.season} Week {meta.week}. Projections are estimates, not guarantees —
        reference lines are EdgeFinder&apos;s own, not sportsbook lines.
      </p>
    </div>
  );
}
