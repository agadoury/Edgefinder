"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  ArrowDown,
  ArrowDownRight,
  ArrowUp,
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
import { fairLine, probOver, sliderDomain, snap } from "../lib/prob";
import { UNIT_SHORT, callOutcome, fmtLine, fmtSigned, fmtStat, leanLabel } from "../lib/format";
import { TIER_SCALE_COPY } from "../lib/tiers";
import { useReveal } from "./RevealContext";
import { usePickem } from "./PickemContext";
import {
  ConfidenceBadge,
  HitMissMark,
  LeanPill,
  ResultBadge,
  ResultTip,
  ResultsToggleName,
  StrengthMeter,
} from "./ui";
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

const LADDER_STEPS = [-2, -1, 0, 1, 2];

export function MarketCard({
  prop,
  market,
  first,
  playerId,
  recentGames,
  coverage80,
}: {
  prop: PlayerProp;
  market: MarketMeta;
  first: string;
  playerId: string;
  recentGames: RecentGame[];
  /** This market's real backtest coverage of the p10–p90 band, from meta.json. */
  coverage80?: number | null;
}) {
  const { revealed } = useReveal();
  const pickem = usePickem();
  const [line, setLine] = useState(prop.refLine);
  // Text being typed into the "Your line" box; null = mirror the active line.
  const [lineText, setLineText] = useState<string | null>(null);
  const [clampNote, setClampNote] = useState<string | null>(null);
  const [showGames, setShowGames] = useState(false);
  const [showLadder, setShowLadder] = useState(false);

  const domain = useMemo(
    () => sliderDomain(prop.probCurve, prop.refLine, market.lineStep),
    [prop.probCurve, prop.refLine, market.lineStep]
  );
  const lo = prop.probCurve[0].line;
  const hi = prop.probCurve[prop.probCurve.length - 1].line;
  const fair = useMemo(() => {
    const f = fairLine(prop.probCurve);
    return f === null ? null : Math.round(f * 10) / 10;
  }, [prop.probCurve]);

  const pOver = probOver(prop.probCurve, line);
  const pUnder = 1 - pOver;
  const unit = UNIT_SHORT[prop.market];
  const decimals = 1;
  const outcome = callOutcome(prop.lean, prop.result);
  const atRef = Math.abs(line - prop.refLine) < 1e-9;

  // Slider stays on its lineStep grid even when a finer line was typed.
  const sliderValue = Math.min(
    domain.max,
    Math.max(domain.min, snap(line, market.lineStep, prop.refLine))
  );

  const updateLine = (v: number) => {
    setLine(v);
    setLineText(null);
    setClampNote(null);
  };

  const commitTyped = () => {
    if (lineText === null) return;
    const parsed = Number(lineText.trim());
    if (lineText.trim() === "" || !Number.isFinite(parsed)) {
      setLineText(null);
      setClampNote(lineText.trim() === "" ? null : "Numbers only — try something like 250.5.");
      return;
    }
    const clamped = Math.min(hi, Math.max(lo, parsed));
    setLine(Math.round(clamped * 100) / 100);
    setLineText(null);
    setClampNote(
      clamped !== parsed
        ? `Our outcome curve covers ${fmtLine(lo)}–${fmtLine(hi)} here, so we pulled you to the edge.`
        : null
    );
  };

  const ladder = useMemo(
    () =>
      LADDER_STEPS.map((k) => snap(prop.refLine + k * market.lineStep, market.lineStep, prop.refLine)),
    [prop.refLine, market.lineStep]
  );

  const myPick = pickem.enabled ? pickem.pickFor(playerId, prop.market) : undefined;
  const awaitingPick = pickem.enabled && myPick === undefined;

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

  const gamesVsLine = (vsLine: number) => {
    const overCount = playedGames.filter((g) => (g.stats[prop.market] ?? 0) > vsLine).length;
    return (
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
          Last {playedGames.length} games vs {awaitingPick ? "the line" : "your line"}
          <span className="tnum ml-auto text-xs font-medium text-ink3">
            cleared {fmtLine(vsLine)} in {overCount} of {playedGames.length}
          </span>
        </button>
        {showGames && (
          <div className="fade-up mt-4">
            <Last10Chart games={playedGames} market={prop.market} line={vsLine} />
          </div>
        )}
      </div>
    );
  };

  // ---------- Pick 'em: projection-neutral state until the pick is locked ----------
  if (awaitingPick) {
    return (
      <section className="card p-5 sm:p-6" aria-label={`${market.label} — make your call`}>
        <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h3 className="text-base font-bold tracking-tight">{market.label}</h3>
          <span className="chip border-accent/25 bg-accentdeep/10 font-semibold text-accent">
            <Target className="h-3 w-3" aria-hidden />
            Pick &apos;em
          </span>
          <InfoTip label="Why is the model's take hidden?">
            Pick &apos;em mode hides our lean until you lock your own call — that&apos;s the game.
            Turn it off in the panel above any time to browse freely.
          </InfoTip>
        </header>

        <div className="mt-6 text-center">
          <p className="flex items-center justify-center gap-1 text-[11px] font-semibold tracking-wider text-ink3 uppercase">
            Reference line
            <InfoTip label="What is a reference line?">
              A typical line for this player and stat, set from his season so far. Our yardstick —
              not a sportsbook line.
            </InfoTip>
          </p>
          <p className="tnum mt-1.5 text-[44px] leading-none font-bold tracking-tight">
            {fmtLine(prop.refLine)} <span className="text-sm font-medium text-ink3">{unit}</span>
          </p>
          <p className="mx-auto mt-3 max-w-sm text-sm leading-relaxed text-ink2">
            Will {first} go over or under? Call it before the model tells you.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={() => pickem.lockPick(playerId, prop.market, "over")}
              className="inline-flex h-11 items-center gap-2 rounded-full border border-over/40 bg-over/10 px-6 text-sm font-bold tracking-wide text-over transition-colors hover:bg-over/20"
            >
              <ArrowUp className="h-4 w-4" strokeWidth={3} aria-hidden />
              OVER {fmtLine(prop.refLine)}
            </button>
            <button
              type="button"
              onClick={() => pickem.lockPick(playerId, prop.market, "under")}
              className="inline-flex h-11 items-center gap-2 rounded-full border border-under/40 bg-under/10 px-6 text-sm font-bold tracking-wide text-under transition-colors hover:bg-under/20"
            >
              <ArrowDown className="h-4 w-4" strokeWidth={3} aria-hidden />
              UNDER {fmtLine(prop.refLine)}
            </button>
          </div>
          <p className="mt-4 text-[11px] text-ink3">
            Prediction practice, not a bet slip — and picks lock, so no peeking first.
          </p>
        </div>

        {/* his real recent games are fair research, not a spoiler */}
        {gamesVsLine(prop.refLine)}
      </section>
    );
  }

  // ---------- Pick 'em: you vs the model strip, once a pick exists ----------
  const pickStrip =
    pickem.enabled && myPick ? (
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-accent/20 bg-accentdeep/10 px-4 py-3">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-accent uppercase">
          <Target className="h-3.5 w-3.5" aria-hidden />
          Pick &apos;em
        </span>
        <span className="text-sm text-ink2">
          Your call:{" "}
          <strong className={myPick === "over" ? "text-over" : "text-under"}>
            {myPick.toUpperCase()}
          </strong>
          <span className="mx-1.5 text-ink3">·</span>
          model: <strong className="text-ink">{leanLabel(prop.lean)}</strong>{" "}
          <span className="tnum text-xs text-ink3">
            ({Math.round(prop.overProbAtRef * 100)}% over)
          </span>
        </span>
        {revealed ? (
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink2">
            {prop.result === "over" || prop.result === "under" ? (
              <>
                <span className="flex items-center gap-1.5">
                  <HitMissMark outcome={callOutcome(myPick, prop.result)} size={13} />
                  you {myPick === prop.result ? "hit" : "missed"}
                </span>
                <span className="flex items-center gap-1.5">
                  <HitMissMark outcome={outcome} size={13} />
                  {prop.lean === "neutral"
                    ? "model had no lean"
                    : `model ${prop.lean === prop.result ? "hit" : "missed"}`}
                </span>
              </>
            ) : (
              <span className="text-xs text-ink3">
                {prop.result === "dnp"
                  ? `No grade — ${first} didn't play.`
                  : "Dead on the line — nobody gets graded."}
              </span>
            )}
          </span>
        ) : (
          <span className="text-xs text-ink3">
            Flip <ResultsToggleName /> to grade you both.
          </span>
        )}
      </div>
    ) : null;

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
              How hard the model leans on this call, 0–100 — {TIER_SCALE_COPY}. It is conviction
              versus our reference line — not value against a sportsbook.
            </InfoTip>
          </span>
        </span>
      </header>

      {pickStrip}

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
              {coverage80 != null ? (
                <>
                  The middle of the road. In this season&apos;s backtest, the real{" "}
                  {market.label.toLowerCase()} number landed inside this range about{" "}
                  {Math.round(coverage80 * 10)} times out of 10 (
                  {Math.round(coverage80 * 100)}% of calls).
                </>
              ) : (
                <>
                  The middle of the road: we expect the real number to land between these two
                  values most of the time.
                </>
              )}
            </InfoTip>
          </p>
          {fair !== null && (
            <p className="mt-3 flex items-center gap-1">
              <span className="chip tnum border-accent/25 bg-accentdeep/10 font-semibold text-accent">
                Model fair line: {fmtLine(fair)}
              </span>
              <InfoTip label="What is the model's fair line?">
                The line where this becomes a pure 50/50 — the model&apos;s chance of going over
                crosses half exactly here. The further a line sits from this number, the stronger
                the model&apos;s opinion at that line.
              </InfoTip>
            </p>
          )}
          {/* the verdict follows the line being tested — never argue with the slider */}
          {atRef ? (
            <p className="mt-4 text-sm leading-relaxed text-ink2" aria-live="polite">
              {prop.verdict}
            </p>
          ) : (
            <div aria-live="polite">
              <p className="mt-4 text-sm leading-relaxed text-ink2">
                At <strong className="tnum text-ink">{fmtLine(line)}</strong>, we give {first} a{" "}
                <strong className={`tnum ${pOver >= 0.5 ? "text-over" : "text-under"}`}>
                  {Math.round(pOver * 100)}%
                </strong>{" "}
                chance to go over —{" "}
                {pOver >= 0.54
                  ? "the model would take the over there."
                  : pOver <= 0.46
                    ? "the model would take the under there."
                    : "basically a coin flip at that number."}
              </p>
              <p className="mt-1.5 text-xs leading-relaxed text-ink3">
                Our resting call at the {fmtLine(prop.refLine)} reference: {prop.verdict}
              </p>
            </div>
          )}
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
                    onClick={() => updateLine(prop.refLine)}
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
            onChange={updateLine}
            fairLine={fair}
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
              value={sliderValue}
              onChange={(e) =>
                updateLine(snap(Number(e.target.value), market.lineStep, prop.refLine))
              }
              aria-valuetext={`line ${fmtLine(line)}, ${Math.round(pOver * 100)}% over`}
            />
            <span className="flex shrink-0 items-center gap-1.5">
              <label
                htmlFor={`your-line-${prop.market}`}
                className="text-[11px] font-medium text-ink3"
              >
                Your line
              </label>
              <input
                id={`your-line-${prop.market}`}
                type="number"
                inputMode="decimal"
                step="any"
                min={lo}
                max={hi}
                value={lineText ?? String(line)}
                onChange={(e) => setLineText(e.target.value)}
                onBlur={commitTyped}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    commitTyped();
                    (e.target as HTMLInputElement).blur();
                  }
                }}
                className="tnum w-[76px] rounded-lg border border-white/10 bg-white/4 px-2 py-1.5 text-right text-sm font-semibold text-ink transition-colors focus:border-accent2/60"
                aria-label={`Type your book's ${market.label} line`}
              />
              <InfoTip label="What does the your-line box do?" align="right">
                Type the exact line your book offers — even between our slider steps, like 250.5
                against a 249.5 reference — and every readout updates to it.
              </InfoTip>
            </span>
          </div>
          {clampNote && <p className="mt-1 text-center text-[11px] text-push">{clampNote}</p>}
          <p className="mt-1 text-center text-[11px] text-ink3">
            Drag to test any line — or type your book&apos;s exact number. The shaded part of the
            curve is {first}&apos;s chance to clear it.
          </p>

          {/* alt-line ladder */}
          <div className="mt-3 flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setShowLadder((v) => !v)}
              aria-expanded={showLadder}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink2 transition-colors hover:text-ink"
            >
              <ChevronDown
                className={`h-3.5 w-3.5 transition-transform ${showLadder ? "rotate-180" : ""}`}
                aria-hidden
              />
              Alt-line ladder
            </button>
            <InfoTip label="What is the alt-line ladder?">
              The model&apos;s odds at lines near the reference — the same curve you&apos;re
              dragging, read at five fixed rungs. Tap a rung to jump the line there.
            </InfoTip>
          </div>
          {showLadder && (
            <div className="fade-up mt-2 overflow-hidden rounded-xl border border-white/8">
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr className="border-b border-white/8 bg-white/3 text-left">
                    <th
                      scope="col"
                      className="px-3 py-2 text-[10px] font-semibold tracking-wider text-ink3 uppercase"
                    >
                      Line
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-2 text-[10px] font-semibold tracking-wider text-ink3 uppercase"
                    >
                      P(over)
                    </th>
                    <th
                      scope="col"
                      className="px-3 py-2 text-[10px] font-semibold tracking-wider text-ink3 uppercase"
                    >
                      P(under)
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ladder.map((rung) => {
                    const p = probOver(prop.probCurve, rung);
                    const isCurrent = Math.abs(rung - line) < 1e-9;
                    const isRef = Math.abs(rung - prop.refLine) < 1e-9;
                    return (
                      <tr
                        key={rung}
                        className={`border-b border-white/5 transition-colors last:border-0 ${
                          isCurrent ? "bg-accentdeep/15" : "hover:bg-white/3"
                        }`}
                      >
                        <td className="px-3 py-1.5">
                          <button
                            type="button"
                            onClick={() => updateLine(rung)}
                            aria-label={`Test the ${fmtLine(rung)} line`}
                            className="inline-flex items-center gap-1.5"
                          >
                            <span className="tnum font-semibold text-ink">{fmtLine(rung)}</span>
                            {isRef && (
                              <span className="text-[10px] font-medium text-ink3">ref</span>
                            )}
                            {isCurrent && !atRef && (
                              <span className="text-[10px] font-semibold text-accent2">
                                your line
                              </span>
                            )}
                          </button>
                        </td>
                        <td
                          className={`tnum px-3 py-1.5 ${
                            p >= 0.5 ? "font-bold text-over" : "text-ink3"
                          }`}
                        >
                          {Math.round(p * 100)}%
                        </td>
                        <td
                          className={`tnum px-3 py-1.5 ${
                            p < 0.5 ? "font-bold text-under" : "text-ink3"
                          }`}
                        >
                          {Math.round((1 - p) * 100)}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
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
          <span className="inline-flex items-center gap-1.5">
            <ResultBadge result={prop.result} actual={prop.actual} unit={unit} />
            <ResultTip result={prop.result} />
          </span>
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
              <span>
                Spoiler — flip <ResultsToggleName /> in the header
              </span>
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
      {gamesVsLine(line)}
    </section>
  );
}
