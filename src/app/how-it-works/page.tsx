import type { Metadata } from "next";
import {
  ArrowRight,
  BrainCircuit,
  Database,
  ListChecks,
  ShieldAlert,
} from "lucide-react";
import { getMeta, type CalibrationBucket, type MarketId } from "../../lib/data";
import { CalibrationChart } from "../../components/charts/CalibrationChart";
import { MARKET_LONG, UNIT_SHORT } from "../../lib/format";
import { TIER_SCALE_COPY } from "../../lib/tiers";

export const metadata: Metadata = {
  title: "How it works — EdgeFinder",
  description:
    "What our AI model watches, how it makes a call, and exactly how honest its track record is.",
};

const STEPS = [
  {
    icon: Database,
    title: "Data we watch",
    body: "Box scores from four full seasons, who's playing and how much, opposing defenses, Vegas totals and spreads, stadium roofs, wind and temperature. All of it, every week.",
  },
  {
    icon: BrainCircuit,
    title: "The model",
    body: "Our AI model learned from four seasons of NFL games (2021–2024). For each player it predicts a full range of outcomes for this exact matchup — not just one number — and never peeks at the game it's predicting.",
  },
  {
    icon: ListChecks,
    title: "What you see",
    body: "A projection, an over/under lean against our reference line, how hard the model leans, and the why — matchup, form, weather — in plain English.",
  },
];

const GLOSSARY = [
  {
    term: "Projection",
    def: "Our model's single best estimate for a stat — the middle of its predicted range.",
  },
  {
    term: "Reference line",
    def: "A typical line for that player and stat, set from his season so far. Our yardstick — not a sportsbook line.",
  },
  {
    term: "Over / under lean",
    def: "The side of the reference line the model would take. When it's basically a coin flip, we say so and take no lean.",
  },
  {
    term: "Strength",
    def: `How hard the model leans, from 0 to 100 — in plain words, ${TIER_SCALE_COPY}. Conviction against our line — not betting value.`,
  },
  {
    term: "Confidence",
    def: "How much trustworthy signal the model had. Steady playing time raises it; injury doubt and small samples lower it.",
  },
  {
    term: "P(over)",
    def: "The model's chance a player clears the line, from its full range of outcomes. Below 50% favors the under.",
  },
  {
    term: "Hit",
    def: "The real number landed on the side we leaned. We count hits and misses at equal weight — that's the whole point of the receipts.",
  },
  {
    term: "Miss",
    def: "The real number landed on the other side of our lean. Misses stay on the board forever, right next to the hits.",
  },
  {
    term: "Push",
    def: "The real number landed exactly on the line. Nobody wins, nobody loses — a push gets no grade and never counts in our record.",
  },
  {
    term: "DNP",
    def: "Did not play. The player sat out (injury, rest, inactive), so the call gets no grade and never counts in our record — including every hit rate on this page.",
  },
  {
    term: "Prop",
    def: "Industry shorthand for “proposition” — a single player-stat line like 249.5 passing yards. You'll mostly see us say call (our read) on a market (the stat).",
  },
];

export default function HowItWorks() {
  const meta = getMeta();
  const bm = meta.backtest.byMarket;
  const passYds = bm.pass_yds;

  const calibration: Partial<Record<MarketId, CalibrationBucket[]>> = {};
  for (const m of meta.markets) {
    const entry = bm[m.id];
    if (entry) calibration[m.id] = entry.calibration;
  }
  const labels = Object.fromEntries(meta.markets.map((m) => [m.id, m.label]));

  // Range copy is derived from the shipped backtest so it can never overstate the model.
  const coverages = meta.markets
    .map((m) => bm[m.id]?.coverage80)
    .filter((c): c is number => c != null);
  const covLo = Math.round(Math.min(...coverages) * 100);
  const covHi = Math.round(Math.max(...coverages) * 100);
  const glossary = [
    ...GLOSSARY,
    {
      term: "Projected range",
      def: `The band we expect the real number to land in most weeks. In this season's backtest it caught the real number ${covLo}–${covHi}% of the time, depending on the stat — each market's exact figure is in the report card above.`,
    },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 pt-14 sm:px-6">
      {/* ---------- intro ---------- */}
      <header className="max-w-2xl">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          No black box.
          <br />
          <span className="accent-text">Here&apos;s the whole machine.</span>
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-ink2">
          EdgeFinder is an AI model with receipts. This page explains what it watches, how it makes
          a call, and exactly how often it&apos;s been right — including when it&apos;s been wrong.
        </p>
      </header>

      {/* ---------- 3 steps ---------- */}
      <section aria-label="How a call is made" className="mt-12">
        <ol className="grid gap-4 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="relative">
              <div className="card card-hover h-full p-5">
                <div className="flex items-center gap-3">
                  <span className="accent-gradient inline-flex h-10 w-10 items-center justify-center rounded-xl shadow-lg shadow-accentdeep/25">
                    <s.icon className="h-5 w-5 text-white" aria-hidden />
                  </span>
                  <span className="text-xs font-bold tracking-wider text-ink3">STEP {i + 1}</span>
                </div>
                <h2 className="mt-3 text-lg font-bold">{s.title}</h2>
                <p className="mt-2 text-sm leading-relaxed text-ink2">{s.body}</p>
              </div>
              {i < STEPS.length - 1 && (
                <ArrowRight
                  className="absolute top-1/2 -right-4 z-10 hidden h-5 w-5 -translate-y-1/2 text-ink3 md:block"
                  aria-hidden
                />
              )}
            </li>
          ))}
        </ol>
      </section>

      {/* ---------- honest model card ---------- */}
      <section aria-label="Model report card" className="mt-16">
        <h2 className="text-2xl font-bold tracking-tight">The honest report card</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink2">
          Before this replayed week, we graded the model on every earlier week of the{" "}
          {meta.backtest.season} season — {meta.backtest.weeksEvaluated} weeks, thousands of calls,
          zero peeking. In plain words: our passing-yards call lands within about{" "}
          <strong className="text-ink">{Math.round(passYds?.mae ?? 0)} yards</strong> of the real
          number on average, and about{" "}
          <strong className="text-ink">
            {Math.round((passYds?.coverage80 ?? 0) * 10)} times out of 10
          </strong>{" "}
          the real passing-yards number lands inside our projected range — every market&apos;s
          exact figure is in the table below.
        </p>

        {/* phones get stacked per-market cards — no five-column squeeze */}
        <div className="mt-6 grid gap-3 sm:hidden">
          {meta.markets.map((m) => {
            const e = bm[m.id];
            if (!e) return null;
            const rows = [
              {
                label: "Avg. miss",
                value: (
                  <>
                    ±{e.mae} <span className="text-xs text-ink3">{UNIT_SHORT[m.id]}</span>
                  </>
                ),
              },
              {
                label: "Simple guess misses by",
                value: (
                  <>
                    ±{e.baselineMae}{" "}
                    <span className="text-xs text-accent2">
                      (we&apos;re {Math.round(((e.baselineMae - e.mae) / e.baselineMae) * 100)}%
                      tighter)
                    </span>
                  </>
                ),
              },
              { label: "Real number inside range", value: <>{Math.round(e.coverage80 * 100)}%</> },
              {
                label: "Strong calls that hit",
                value: (
                  <>
                    {Math.round(e.strongCallHitRate * 100)}%{" "}
                    <span className="text-xs text-ink3">of {e.strongCallN}</span>
                  </>
                ),
              },
            ];
            return (
              <div key={m.id} className="card p-4">
                <h3 className="text-sm font-bold">{MARKET_LONG[m.id]}</h3>
                <dl className="mt-2.5 grid gap-1.5">
                  {rows.map((r) => (
                    <div key={r.label} className="flex items-baseline justify-between gap-3">
                      <dt className="text-xs text-ink3">{r.label}</dt>
                      <dd className="tnum text-sm font-semibold text-ink">{r.value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            );
          })}
          <p className="px-1 text-xs leading-relaxed text-ink3">
            “Simple guess” = just using the player&apos;s recent median — the bar any model has to
            beat. “Strong calls” are leans with strength 60+. Evaluated on {meta.backtest.season}{" "}
            weeks 1–{meta.backtest.weeksEvaluated}; model {meta.modelVersion}.
          </p>
        </div>

        <div className="card mt-6 hidden overflow-hidden sm:block">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-white/8 bg-white/2 text-left">
                  <th scope="col" className="px-4 py-3 text-[11px] font-semibold tracking-wider text-ink3 uppercase">
                    Market
                  </th>
                  <th scope="col" className="px-4 py-3 text-[11px] font-semibold tracking-wider text-ink3 uppercase">
                    Avg. miss
                  </th>
                  <th scope="col" className="px-4 py-3 text-[11px] font-semibold tracking-wider text-ink3 uppercase">
                    Simple guess misses by
                  </th>
                  <th scope="col" className="px-4 py-3 text-[11px] font-semibold tracking-wider text-ink3 uppercase">
                    Real number inside range
                  </th>
                  <th scope="col" className="px-4 py-3 text-[11px] font-semibold tracking-wider text-ink3 uppercase">
                    Strong calls that hit
                  </th>
                </tr>
              </thead>
              <tbody>
                {meta.markets.map((m) => {
                  const e = bm[m.id];
                  if (!e) return null;
                  return (
                    <tr key={m.id} className="border-b border-white/5 last:border-0">
                      <td className="px-4 py-3 font-semibold">{MARKET_LONG[m.id]}</td>
                      <td className="tnum px-4 py-3">
                        ±{e.mae} <span className="text-xs text-ink3">{UNIT_SHORT[m.id]}</span>
                      </td>
                      <td className="tnum px-4 py-3 text-ink2">
                        ±{e.baselineMae}{" "}
                        <span className="text-xs text-accent2">
                          (we&apos;re {Math.round(((e.baselineMae - e.mae) / e.baselineMae) * 100)}%
                          tighter)
                        </span>
                      </td>
                      <td className="tnum px-4 py-3">{Math.round(e.coverage80 * 100)}%</td>
                      <td className="tnum px-4 py-3">
                        {Math.round(e.strongCallHitRate * 100)}%{" "}
                        <span className="text-xs text-ink3">of {e.strongCallN}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="border-t border-white/6 px-4 py-3 text-xs leading-relaxed text-ink3">
            “Simple guess” = just using the player&apos;s recent median — the bar any model has to
            beat. “Strong calls” are leans with strength 60+. Evaluated on {meta.backtest.season}{" "}
            weeks 1–{meta.backtest.weeksEvaluated}; model {meta.modelVersion}.
          </p>
        </div>
      </section>

      {/* ---------- calibration ---------- */}
      <section aria-label="Calibration" className="mt-16 grid items-start gap-8 lg:grid-cols-2">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">
            When we say 60%, does it happen 60% of the time?
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-ink2">
            That&apos;s the fairest test of any prediction. We grouped every call the model made
            this season by its stated chance, then checked how often each group actually came true.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-ink2">
            Each dot is one group of calls.{" "}
            <strong className="text-ink">Dots on the gray diagonal mean the percentage was
            honest</strong> — when we said 60%, it happened about 60% of the time. Dots below the
            line mean we were a touch overconfident; above it, a touch shy. Ours hug the line, with
            a little natural wobble at the extremes.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-ink2">
            This is also why we never show 95% calls on NFL player stats — football is too noisy
            for that, and any tool that claims otherwise is selling something.
          </p>
        </div>
        <div className="card p-5">
          <CalibrationChart byMarket={calibration} labels={labels} />
        </div>
      </section>

      {/* ---------- glossary ---------- */}
      <section aria-label="Glossary" className="mt-16">
        <h2 className="text-2xl font-bold tracking-tight">The words we use</h2>
        <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {glossary.map((g) => (
            <div key={g.term} className="card p-4">
              <dt className="text-sm font-bold text-accent">{g.term}</dt>
              <dd className="mt-1.5 text-sm leading-relaxed text-ink2">{g.def}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* ---------- honesty ---------- */}
      <section
        aria-label="What we won't pretend"
        className="card mt-16 border-push/20 p-6"
      >
        <div className="flex items-start gap-4">
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-push/25 bg-push/10">
            <ShieldAlert className="h-5 w-5 text-push" aria-hidden />
          </span>
          <div>
            <h2 className="text-lg font-bold">What we won&apos;t pretend</h2>
            <ul className="mt-3 grid gap-2.5 text-sm leading-relaxed text-ink2 lg:grid-cols-3 lg:gap-6">
              <li>
                <strong className="text-ink">Reference lines are not sportsbook lines.</strong>{" "}
                They&apos;re our own yardstick. Books shade their numbers for their own reasons —
                always compare before you act.
              </li>
              <li>
                <strong className="text-ink">Projections are estimates, not guarantees.</strong>{" "}
                Football is chaotic on purpose. A 60% call loses 4 times out of 10 — that&apos;s
                what 60% means.
              </li>
              <li>
                <strong className="text-ink">Past accuracy doesn&apos;t promise the future.</strong>{" "}
                We publish the track record so you can judge us, not so you&apos;ll assume it
                repeats.
              </li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}
