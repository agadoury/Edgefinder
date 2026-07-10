import Link from "next/link";
import { ArrowRight, BrainCircuit, ReceiptText, ShieldCheck } from "lucide-react";
import { getHeadshots, getMeta, getSlate } from "../lib/data";
import { getAvailabilityWatch } from "../lib/availability";
import { Board } from "../components/Board";
import { GameCard } from "../components/GameCard";
import { HeroVisual } from "../components/HeroVisual";
import { RevealCTA } from "../components/RevealCTA";
import { WelcomeTour } from "../components/WelcomeTour";
import { InfoTip } from "../components/Tooltip";

export default function Home() {
  const meta = getMeta();
  const slate = getSlate();
  const passYds = meta.backtest.byMarket.pass_yds;

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6">
      {/* ---------- first-visit orientation (dismissable, never a modal) ---------- */}
      <WelcomeTour />

      {/* ---------- hero ---------- */}
      <section className="relative pt-10 pb-10 sm:pt-16">
        <div className="absolute top-20 right-0 xl:right-4">
          <HeroVisual />
        </div>
        <div className="max-w-3xl lg:max-w-xl xl:max-w-2xl">
          <span className="chip mb-5 border-accent/25 bg-accentdeep/10 text-accent">
            <BrainCircuit className="h-3.5 w-3.5" aria-hidden />
            Our AI model · trained on four NFL seasons ({meta.trainSeasons[0]}–
            {meta.trainSeasons[meta.trainSeasons.length - 1]})
          </span>
          <h1 className="text-4xl leading-[1.05] font-bold tracking-tight sm:text-6xl">
            Know what to expect
            <br />
            <span className="accent-text">before you bet.</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink2">
            EdgeFinder projects every big player stat — passing, rushing, catching — and explains
            each number in plain English. No jargon, no black box. Just the matchup, the form, the
            weather, and how hard our model leans.
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <a
              href="#board"
              className="accent-gradient inline-flex h-11 items-center gap-2 rounded-full px-6 text-sm font-semibold text-white shadow-lg shadow-accentdeep/30 transition-all hover:brightness-110"
            >
              See this week&apos;s calls
              <ArrowRight className="h-4 w-4" aria-hidden />
            </a>
            <Link
              href="/how-it-works"
              className="inline-flex h-11 items-center rounded-full border border-white/12 bg-white/4 px-6 text-sm font-semibold text-ink2 transition-colors hover:border-white/25 hover:text-ink"
            >
              How it works
            </Link>
          </div>
        </div>

        {/* proof points — 3-up even on phones so the board stays close to the top */}
        <dl className="mt-8 grid max-w-3xl grid-cols-3 gap-2 sm:mt-10 sm:gap-3">
          <div className="card px-2.5 py-2.5 sm:px-4 sm:py-3">
            <dt className="flex items-center gap-1 text-[10px] leading-tight text-ink3 sm:text-xs">
              <span>
                Avg. passing-yards <span className="whitespace-nowrap">miss</span>
              </span>
              <InfoTip label="What does average miss mean?">
                Across {meta.backtest.weeksEvaluated} weeks of {meta.backtest.season}, our
                passing-yards call landed within about {Math.round(passYds?.mae ?? 0)} yards of the
                real number, on average.
              </InfoTip>
            </dt>
            <dd className="tnum mt-1 text-lg font-bold sm:text-2xl">
              ±{Math.round(passYds?.mae ?? 0)}{" "}
              <span className="text-xs font-medium text-ink3 sm:text-sm">yds</span>
            </dd>
          </div>
          <div className="card px-2.5 py-2.5 sm:px-4 sm:py-3">
            <dt className="flex items-center gap-1 text-[10px] leading-tight text-ink3 sm:text-xs">
              Range coverage
              <InfoTip label="What does range coverage mean?">
                About {Math.round((passYds?.coverage80 ?? 0) * 10)} times out of 10 this season,
                the real passing-yards number landed inside the projected range we show on every
                player page. Other stats vary — the report card has each one.
              </InfoTip>
            </dt>
            <dd className="tnum mt-1 text-lg font-bold sm:text-2xl">
              {Math.round((passYds?.coverage80 ?? 0) * 100)}
              <span className="text-xs font-medium text-ink3 sm:text-sm">%</span>
            </dd>
          </div>
          <div className="card px-2.5 py-2.5 sm:px-4 sm:py-3">
            <dt className="flex items-center gap-1 text-[10px] leading-tight text-ink3 sm:text-xs">
              Weeks back-tested
              <InfoTip label="What is back-testing?">
                We replayed every earlier {meta.backtest.season} week the same way we replay this
                one — the model never sees the game it is predicting.
              </InfoTip>
            </dt>
            <dd className="tnum mt-1 text-lg font-bold sm:text-2xl">
              {meta.backtest.weeksEvaluated}
            </dd>
          </div>
        </dl>
      </section>

      {/* ---------- replay banner ---------- */}
      <section
        aria-label="Replay mode"
        className="card relative overflow-hidden border-accent/20 p-5 sm:p-6"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(600px 200px at 12% 0%, rgba(99,102,241,0.18), transparent 60%)",
          }}
        />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center">
          <span className="accent-gradient inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl shadow-lg shadow-accentdeep/30">
            <ReceiptText className="h-5.5 w-5.5 text-white" aria-hidden />
          </span>
          <div className="flex-1">
            <h2 className="text-base font-bold">
              You&apos;re replaying Week {meta.week} of the {meta.season} season.
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-ink2">
              Every call below was locked before kickoff, and the real outcomes exist — so we show
              our receipts. Flip on results any time and check us, call by call.
            </p>
          </div>
          <RevealCTA />
        </div>
      </section>

      {/* ---------- games strip: swipeable on phones, grid on desktop ---------- */}
      <section aria-label="This week's games" className="mt-10 sm:mt-12">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-bold tracking-tight">Week {meta.week} slate</h2>
          <span className="text-xs text-ink3">
            <span className="md:hidden">
              {slate.games.length} games · swipe → · times ET
            </span>
            <span className="hidden md:inline">Tap a game for its calls · all times Eastern</span>
          </span>
        </div>
        <ul
          className="no-scrollbar -mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1 md:mx-0 md:grid md:snap-none md:grid-cols-3 md:gap-4 md:overflow-visible md:px-0 md:pb-0"
          aria-label={`${slate.games.length} games — scrolls horizontally on small screens`}
        >
          {slate.games.map((g) => (
            <li
              key={g.gameId}
              className="w-[80%] max-w-[300px] shrink-0 snap-start md:w-auto md:max-w-none"
            >
              <GameCard
                game={g}
                callCount={slate.props.filter((p) => p.gameId === g.gameId).length}
              />
            </li>
          ))}
        </ul>
      </section>

      {/* ---------- board ---------- */}
      <section className="mt-10 scroll-mt-24 sm:mt-14" id="board">
        <div className="mb-1 flex items-center gap-2">
          <h2 className="text-2xl font-bold tracking-tight">This Week&apos;s Top Calls</h2>
        </div>
        <p className="mb-5 max-w-2xl text-sm text-ink2">
          Every projection is measured against our own{" "}
          <span className="inline-flex items-center gap-1 font-medium text-ink">
            reference line
            <InfoTip label="What is a reference line?">
              A typical line for this player and stat, set from his season so far. It is our
              yardstick — not a sportsbook line.
            </InfoTip>
          </span>{" "}
          — click any row for the full story.
        </p>
        <Board
          rows={slate.props}
          games={slate.games}
          markets={meta.markets}
          headshots={getHeadshots()}
          availability={getAvailabilityWatch()}
        />
      </section>

      {/* ---------- honesty strip ---------- */}
      <section className="card mt-14 flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
        <ShieldCheck className="h-5 w-5 shrink-0 text-accent2" aria-hidden />
        <p className="text-sm leading-relaxed text-ink2">
          Projections are estimates, not guarantees. Reference lines are ours, not a
          sportsbook&apos;s. We publish our misses right next to our hits —{" "}
          <Link
            href="/how-it-works"
            className="font-semibold text-accent underline decoration-accent/40 underline-offset-4 hover:text-accent2"
          >
            see exactly how the model is graded
          </Link>
          .
        </p>
      </section>
    </div>
  );
}
