import { ReceiptText } from "lucide-react";
import type { HistoryCall } from "../lib/data";
import { MARKET_SHORT, callOutcome, fmtLine, fmtStat, leanLabel } from "../lib/format";
import { HitMissMark, LeanPill } from "./ui";
import { InfoTip } from "./Tooltip";

/**
 * Model receipts: the model's earlier 2025 calls on this player. These weeks
 * already happened before the replayed week, so they're always visible —
 * that's the point.
 */
export function Receipts({ history, first }: { history: HistoryCall[]; first: string }) {
  const graded = history.filter((h) => callOutcome(h.lean, h.result) === "hit" || callOutcome(h.lean, h.result) === "miss");
  const hits = graded.filter((h) => callOutcome(h.lean, h.result) === "hit").length;
  const rate = graded.length > 0 ? Math.round((hits / graded.length) * 100) : 0;

  return (
    <section className="card p-5 sm:p-6" aria-label="Model receipts">
      <header className="flex flex-wrap items-center gap-3">
        <span className="accent-gradient inline-flex h-8 w-8 items-center justify-center rounded-lg">
          <ReceiptText className="h-4 w-4 text-white" aria-hidden />
        </span>
        <h3 className="text-base font-bold tracking-tight">Model receipts</h3>
        <InfoTip label="What are model receipts?">
          Every call our model made on {first} earlier this season, graded against what really
          happened. No cherry-picking — misses included.
        </InfoTip>
        <span className="chip tnum ml-auto border-accent/25 bg-accentdeep/10 font-semibold text-accent">
          {hits} of {graded.length} leans hit · {rate}%
        </span>
      </header>

      <ul className="mt-4 divide-y divide-white/5">
        {history.map((h) => {
          const outcome = callOutcome(h.lean, h.result);
          return (
            <li
              key={`${h.week}-${h.market}`}
              className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2.5"
            >
              <span className="tnum w-12 shrink-0 text-xs font-semibold text-ink3">
                Wk {h.week}
              </span>
              <span className="w-24 shrink-0 text-xs font-medium text-ink2">
                {MARKET_SHORT[h.market]}
              </span>
              <span className="tnum text-xs text-ink3">
                proj <span className="font-semibold text-ink2">{fmtStat(h.projection)}</span> · line{" "}
                <span className="font-semibold text-ink2">{fmtLine(h.refLine)}</span>
              </span>
              <LeanPill lean={h.lean} size="sm" />
              <span className="ml-auto flex items-center gap-2.5">
                <span
                  className={`tnum text-sm font-bold ${
                    h.result === "over"
                      ? "text-over"
                      : h.result === "under"
                        ? "text-under"
                        : "text-ink2"
                  }`}
                >
                  {fmtStat(h.actual)}
                </span>
                <span className="w-12 text-right text-[10px] font-bold tracking-wider text-ink3 uppercase">
                  {h.result === "dnp" ? "DNP" : h.result}
                </span>
                <HitMissMark outcome={outcome} size={13} />
              </span>
              <span className="sr-only">
                Week {h.week}, {MARKET_SHORT[h.market]}: projected {fmtStat(h.projection)} against a{" "}
                {fmtLine(h.refLine)} line, lean {leanLabel(h.lean)}, actual {fmtStat(h.actual)} —{" "}
                {outcome === "hit" ? "hit" : outcome === "miss" ? "miss" : "no grade"}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
