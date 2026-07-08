"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CalendarClock,
  ChevronDown,
  EyeOff,
  Home,
  RotateCcw,
  Shield,
  Target,
  TrendingUp,
  UserRound,
  Wind,
  type LucideIcon,
} from "lucide-react";
import type { FactorGroup, MarketMeta, PlayerProp, RecentGame } from "../lib/data";
import { probOver, sliderDomain, snap } from "../lib/prob";
import { UNIT_SHORT, callOutcome, fmtLine, fmtSigned, fmtStat } from "../lib/format";
import { useReveal } from "./RevealContext";
import { ConfidenceBadge, HitMissMark, LeanPill, ResultBadge, StrengthMeter } from "./ui";
import { InfoTip } from "./Tooltip";
import { CountUp } from "./CountUp";
import { DistributionChart } from "./charts/DistributionChart";
import { Last10Chart } from "./charts/Last10Chart";

const GROUP_ICON: Record<FactorGroup, LucideIcon> = {
  recent_form: TrendingUp,
  usage_role: Target,
  opp_defense: Shield,
  game_environment: Activity,
  weather: Wind,
  rest_schedule: CalendarClock,
  qb_situation: UserRound,
  home_away: Home,
};

const GROUP_LABEL: Record<FactorGroup, string> = {
  recent_form: "Form",
  usage_role: "Role",
  opp_defense: "Matchup",
  game_environment: "Game script",
  weather: "Weather",
  rest_schedule: "Rest",
  qb_situation: "Quarterback",
  home_away: "Venue",
};

export function MarketCard({
  prop,
  market,
  first,
  recentGames,
}: {
  prop: PlayerProp;
  market: MarketMeta;
  first: string;
  recentGames: RecentGame[];
}) {
  const { revealed } = useReveal();
  const [line, setLine] = useState(prop.refLine);
  const [showGames, setShowGames] = useState(false);

  const domain = useMemo(
    () => sliderDomain(prop.probCurve, prop.refLine, market.lineStep),
    [prop.probCurve, prop.refLine, market.lineStep]
  );
  const pOver = probOver(prop.probCurve, line);
  const pUnder = 1 - pOver;
  const unit = UNIT_SHORT[prop.market];
  const decimals = 1;
  const outcome = callOutcome(prop.lean, prop.result);
  const atRef = Math.abs(line - prop.refLine) < 1e-9;

  const actualColor =
    prop.result === "over" ? "#34d399" : prop.result === "under" ? "#f87171" : "#fbbf24";

  const resultSentence = (() => {
    if (prop.result === "dnp") return `${first} didn't play, so this call gets no grade.`;
    if (prop.result === "push") return `Dead on the line — a push. Nobody wins, nobody loses.`;
    const word = prop.result === "over" ? "over" : "under";
    if (outcome === "hit")
      return `${first} finished ${word} the ${fmtLine(prop.refLine)} line — our call hit.`;
    if (outcome === "miss")
      return `${first} finished ${word} the ${fmtLine(prop.refLine)} line — our lean missed. We take the L.`;
    return `${first} finished ${word} the line — we had no lean on this one.`;
  })();

  const playedGames = useMemo(
    () => recentGames.filter((g) => g.stats[prop.market] !== undefined),
    [recentGames, prop.market]
  );
  const overCount = playedGames.filter((g) => (g.stats[prop.market] ?? 0) > line).length;

  return (
    <section className="card p-5 sm:p-6" aria-label={`${market.label} projection`}>
      {/* header */}
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h3 className="text-base font-bold tracking-tight">{market.label}</h3>
        <LeanPill lean={prop.lean} size="sm" />
        <span className="ml-auto flex items-center gap-4">
          <span className="flex items-center gap-1">
            <ConfidenceBadge confidence={prop.confidence} />
            <InfoTip label="What does confidence mean?" align="right">
              How much trustworthy signal the model had for this exact call — steady playing time
              raises it, injury doubt and small samples lower it.
            </InfoTip>
          </span>
          <span className="flex items-center gap-1">
            <StrengthMeter value={prop.strength} />
            <InfoTip label="What does strength mean?" align="right">
              How hard the model leans on this call, 0–100. It is conviction versus our reference
              line — not value against a sportsbook.
            </InfoTip>
          </span>
        </span>
      </header>

      <div className="mt-6 grid gap-x-10 gap-y-8 lg:grid-cols-[250px_1fr]">
        {/* projection block */}
        <div>
          <p className="flex items-baseline gap-2">
            <CountUp
              value={prop.projection}
              decimals={decimals}
              className="text-[52px] leading-none font-bold tracking-tight"
            />
            <span className="text-sm font-medium text-ink3">{unit}</span>
          </p>
          <p className="mt-1.5 flex items-center gap-1 text-xs text-ink3">
            projected · range {fmtStat(prop.quantiles.p10)}–{fmtStat(prop.quantiles.p90)}
            <InfoTip label="What is the projected range?">
              The middle of the road: 8 times out of 10 we expect the real number to land between
              these two values.
            </InfoTip>
          </p>
          <p className="mt-4 text-sm leading-relaxed text-ink2">{prop.verdict}</p>
          <p className="mt-3 rounded-lg border border-white/7 bg-white/3 px-3 py-2 text-xs leading-relaxed text-ink3">
            <span className="font-semibold text-ink2">Why this confidence:</span>{" "}
            {prop.confidenceReason}
          </p>
        </div>

        {/* interactive distribution */}
        <div>
          <div className="mb-2 flex items-end justify-between gap-2">
            <div className="min-w-[92px]">
              <p className="text-[11px] font-semibold tracking-wider text-under/90 uppercase">
                Under
              </p>
              <p className="tnum text-2xl leading-tight font-bold text-under">
                {Math.round(pUnder * 100)}%
              </p>
            </div>
            <div className="pb-0.5 text-center">
              <p className="text-[11px] text-ink3">
                {atRef ? "reference line" : "your line"}
                {!atRef && (
                  <button
                    type="button"
                    onClick={() => setLine(prop.refLine)}
                    className="ml-1.5 inline-flex items-center gap-0.5 font-semibold text-accent2 hover:underline"
                  >
                    <RotateCcw className="h-2.5 w-2.5" aria-hidden />
                    reset
                  </button>
                )}
              </p>
              <p className="tnum text-lg leading-tight font-bold text-accent2">{fmtLine(line)}</p>
            </div>
            <div className="min-w-[92px] text-right">
              <p className="text-[11px] font-semibold tracking-wider text-over/90 uppercase">
                Over
              </p>
              <p className="tnum text-2xl leading-tight font-bold text-over">
                {Math.round(pOver * 100)}%
              </p>
            </div>
          </div>

          <DistributionChart
            curve={prop.probCurve}
            value={line}
            refLine={prop.refLine}
            lineStep={market.lineStep}
            onChange={setLine}
            actual={prop.actual}
            actualColor={actualColor}
            showActual={revealed}
            ariaLabel={`Projected ${market.label} outcome curve. ${first} clears ${fmtLine(
              line
            )} in ${Math.round(pOver * 100)} percent of simulations.`}
          />

          <div className="mt-1 flex items-center gap-3">
            <label htmlFor={`slider-${prop.market}`} className="sr-only">
              Move the {market.label} line
            </label>
            <input
              id={`slider-${prop.market}`}
              type="range"
              className="ef-slider flex-1"
              min={domain.min}
              max={domain.max}
              step={market.lineStep}
              value={line}
              onChange={(e) => setLine(snap(Number(e.target.value), market.lineStep, prop.refLine))}
              aria-valuetext={`line ${fmtLine(line)}, ${Math.round(pOver * 100)}% over`}
            />
          </div>
          <p className="text-center text-[11px] text-ink3">
            Drag to test any line — the shaded part of the curve is {first}&apos;s chance to clear
            it.
          </p>
        </div>
      </div>

      {/* what actually happened */}
      <div className="card relative mt-6 overflow-hidden border-white/10 bg-white/2">
        <div
          className="blur-panel flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3"
          data-hidden={!revealed}
          aria-hidden={!revealed}
        >
          <span className="text-[11px] font-bold tracking-wider text-ink3 uppercase">
            What actually happened
          </span>
          <ResultBadge result={prop.result} actual={prop.actual} unit={unit} />
          <HitMissMark outcome={outcome} size={14} />
          <span className="text-sm text-ink2">{resultSentence}</span>
          {prop.actual !== null && (
            <span className="tnum ml-auto text-xs text-ink3">
              model {prop.actual === prop.projection ? "was dead on" : `off by ${fmtStat(Math.abs(prop.actual - prop.projection))} ${unit}`}
            </span>
          )}
        </div>
        {!revealed && (
          <span className="absolute inset-0 z-10 flex items-center justify-center">
            <span className="chip border-white/15 bg-raised/90 font-semibold text-ink2">
              <EyeOff className="h-3.5 w-3.5" aria-hidden />
              Spoiler — flip “Show results” in the header
            </span>
          </span>
        )}
      </div>

      {/* factors */}
      <div className="mt-6">
        <h4 className="flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-ink3 uppercase">
          Why the model says this
          <InfoTip label="Where do these factors come from?">
            The biggest pushes and pulls on this projection, with the live numbers behind them.
            Bigger impact = bigger influence on the final call.
          </InfoTip>
        </h4>
        <ul className="mt-3 grid gap-2.5 xl:grid-cols-2">
          {prop.factors.map((f) => {
            const Icon = GROUP_ICON[f.group];
            const up = f.direction === "up";
            return (
              <li
                key={f.label}
                className="flex items-start gap-3 rounded-xl border border-white/6 bg-white/2 px-3.5 py-3"
              >
                <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/8 bg-white/4 text-accent">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <span className="min-w-0">
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="text-[10px] font-bold tracking-wider text-ink3 uppercase">
                      {GROUP_LABEL[f.group]}
                    </span>
                    <span
                      className={`tnum inline-flex items-center gap-0.5 rounded-full border px-1.5 py-0.5 text-[10px] font-bold ${
                        up
                          ? "border-accent2/25 bg-accent2deep/10 text-accent2"
                          : "border-white/12 bg-white/4 text-ink2"
                      }`}
                      aria-label={`${up ? "raises" : "lowers"} the projection by ${Math.abs(
                        f.impact
                      )} ${unit}`}
                    >
                      {up ? (
                        <ArrowUpRight className="h-3 w-3" aria-hidden />
                      ) : (
                        <ArrowDownRight className="h-3 w-3" aria-hidden />
                      )}
                      {fmtSigned(f.impact)} {unit}
                    </span>
                  </span>
                  <span className="mt-1 block text-sm leading-snug font-semibold text-ink">
                    {f.label}
                  </span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-ink3">{f.detail}</span>
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      {/* last 10 games */}
      <div className="mt-5 border-t border-white/6 pt-4">
        <button
          type="button"
          onClick={() => setShowGames((v) => !v)}
          aria-expanded={showGames}
          className="flex w-full items-center gap-2 text-left text-sm font-semibold text-ink2 transition-colors hover:text-ink"
        >
          <ChevronDown
            className={`h-4 w-4 transition-transform ${showGames ? "rotate-180" : ""}`}
            aria-hidden
          />
          Last {playedGames.length} games vs your line
          <span className="tnum ml-auto text-xs font-medium text-ink3">
            cleared {fmtLine(line)} in {overCount} of {playedGames.length}
          </span>
        </button>
        {showGames && (
          <div className="fade-up mt-4">
            <Last10Chart games={playedGames} market={prop.market} line={line} />
          </div>
        )}
      </div>
    </section>
  );
}
