"use client";

import { RotateCcw, Target } from "lucide-react";
import { useReveal } from "./RevealContext";
import { usePickem } from "./PickemContext";
import { ResultsToggleName } from "./ui";
import { InfoTip } from "./Tooltip";

function fmtRecord(wins: number, losses: number): string {
  return `${wins}–${losses}`;
}

/** Small "Your calls" status chip in the site header. Appears once picks exist. */
export function PickemHeaderChip() {
  const { record } = usePickem();
  const { revealed } = useReveal();
  if (record.locked === 0) return null;
  if (revealed && record.graded > 0) {
    return (
      <span
        className="chip tnum hidden md:inline-flex"
        title="Your Pick 'em record vs the model this week"
      >
        <Target className="h-3 w-3 text-accent2" aria-hidden />
        You {fmtRecord(record.you.wins, record.you.losses)} · model{" "}
        {fmtRecord(record.model.wins, record.model.losses)}
      </span>
    );
  }
  return (
    <span
      className="chip tnum hidden md:inline-flex"
      title="Your locked Pick 'em calls — flip Show results to grade them"
    >
      <Target className="h-3 w-3 text-accent2" aria-hidden />
      {record.locked} {record.locked === 1 ? "call" : "calls"} locked
    </span>
  );
}

/** Compact entry point in the board's filter row. */
export function PickemBoardToggle() {
  const { enabled, setEnabled } = usePickem();
  return (
    <span className="flex items-center gap-1">
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        onClick={() => setEnabled(!enabled)}
        className={`inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-semibold transition-colors ${
          enabled
            ? "border-accent/40 bg-accentdeep/15 text-accent"
            : "border-white/8 bg-white/3 text-ink2 hover:text-ink"
        }`}
      >
        <Target className="h-3.5 w-3.5" aria-hidden />
        Pick &apos;em{enabled ? " · on" : ""}
      </button>
      <InfoTip label="What is Pick 'em mode?">
        Call it before the model tells you: with Pick &apos;em on, player pages hide the
        model&apos;s lean until you lock your own over/under on each stat. Your record vs the model
        is prediction practice — never money, never streaks.
      </InfoTip>
    </span>
  );
}

/**
 * Player-page panel: the opt-in CTA when the mode is off, the "Your calls"
 * ledger when it's on. Money-free by design — the score is you vs the model.
 */
export function PickemPanel() {
  const { enabled, setEnabled, week, record, resetWeek } = usePickem();
  const { revealed } = useReveal();

  if (!enabled) {
    return (
      <section
        aria-label="Pick 'em mode"
        className="card flex flex-col gap-3 border-accent/15 px-5 py-4 sm:flex-row sm:items-center"
      >
        <span className="accent-gradient inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg shadow-lg shadow-accentdeep/25">
          <Target className="h-4.5 w-4.5 text-white" aria-hidden />
        </span>
        <div className="flex-1">
          <h2 className="text-sm font-bold">Call it before the model tells you</h2>
          <p className="mt-0.5 text-xs leading-relaxed text-ink2">
            Turn on Pick &apos;em and each stat below hides our lean until you lock your own
            over/under. Prediction practice, not a bet slip.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEnabled(true)}
          className="accent-gradient inline-flex h-9 shrink-0 items-center gap-2 rounded-full px-4 text-sm font-semibold text-white shadow-lg shadow-accentdeep/30 transition-all hover:brightness-110"
        >
          <Target className="h-4 w-4" aria-hidden />
          Turn on Pick &apos;em
        </button>
      </section>
    );
  }

  return (
    <section
      aria-label="Your Pick 'em calls"
      className="card flex flex-wrap items-center gap-x-4 gap-y-3 border-accent/20 px-5 py-4"
    >
      <span className="accent-gradient inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg shadow-lg shadow-accentdeep/25">
        <Target className="h-4.5 w-4.5 text-white" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <h2 className="flex items-center gap-1.5 text-sm font-bold">
          Your calls · Week {week}
          <InfoTip label="How does Pick 'em scoring work?">
            Every stat card hides the model&apos;s lean until you lock a pick. Once results are on,
            you and the model are graded the same way — hits and misses at equal weight. Pushes and
            DNPs grade nobody.
          </InfoTip>
        </h2>
        <p className="tnum mt-0.5 text-xs text-ink2">
          {record.locked === 0 ? (
            "Nothing locked yet — call over or under on any stat below."
          ) : revealed && record.graded > 0 ? (
            `You ${fmtRecord(record.you.wins, record.you.losses)} · model ${fmtRecord(
              record.model.wins,
              record.model.losses
            )}${record.locked > record.graded ? ` · ${record.locked - record.graded} ungraded` : ""}`
          ) : (
            <>
              {record.locked} {record.locked === 1 ? "call" : "calls"} locked — flip{" "}
              <ResultsToggleName /> to grade them.
            </>
          )}
        </p>
      </div>
      {record.locked > 0 && (
        <button
          type="button"
          onClick={resetWeek}
          className="inline-flex h-8 items-center gap-1.5 rounded-full border border-white/10 bg-white/4 px-3 text-xs font-semibold text-ink2 transition-colors hover:border-white/25 hover:text-ink"
        >
          <RotateCcw className="h-3 w-3" aria-hidden />
          Reset week
        </button>
      )}
      <button
        type="button"
        onClick={() => setEnabled(false)}
        className="h-8 rounded-full px-2 text-xs font-medium text-ink3 transition-colors hover:text-ink"
      >
        Turn off
      </button>
    </section>
  );
}
