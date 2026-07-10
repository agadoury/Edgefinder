"use client";

import { useMemo, useState } from "react";
import type { MarketId, RecentGame } from "../../lib/data";
import { UNIT_SHORT, fmtLine, fmtStat } from "../../lib/format";
import { useMeasuredWidth } from "./useMeasuredWidth";

/**
 * Last-10-games bar chart vs the current slider line. Bars are colored by
 * whether the game cleared the line (green over / red under) — the threshold
 * line itself is the positional backup channel, and every bar has a tooltip.
 */
export function Last10Chart({
  games,
  market,
  line,
}: {
  games: RecentGame[];
  market: MarketId;
  line: number;
}) {
  const { ref: boxRef, width: W } = useMeasuredWidth<HTMLDivElement>(640);
  const H = 190;
  const PAD_L = 34;
  const PAD_R = W < 480 ? 56 : 70;
  const PAD_T = 14;
  const AXIS_H = 22;
  const plotBottom = H - AXIS_H;
  const [hover, setHover] = useState<number | null>(null);

  const ordered = useMemo(() => [...games].reverse(), [games]); // oldest → newest

  // Timeline slots: played games, plus hollow "out" ticks for weeks skipped
  // between two same-season games (injury, rest, or the bye — the box score
  // alone can't say which, so the copy stays honest about that).
  type Slot = { kind: "game"; g: RecentGame } | { kind: "out"; season: number; week: number };
  const slots = useMemo<Slot[]>(() => {
    const out: Slot[] = [];
    for (let i = 0; i < ordered.length; i++) {
      out.push({ kind: "game", g: ordered[i] });
      const cur = ordered[i];
      const nxt = ordered[i + 1];
      if (nxt && cur.season === nxt.season) {
        for (let w = cur.week + 1; w < nxt.week; w++) out.push({ kind: "out", season: cur.season, week: w });
      }
    }
    return out;
  }, [ordered]);

  const maxVal = Math.max(...ordered.map((g) => g.stats[market] ?? 0), line);
  const niceMax = useMemo(() => {
    const raw = maxVal * 1.15;
    const mag = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1))));
    const step = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].map((m) => m * mag).find((s) => s >= raw);
    return step ?? raw;
  }, [maxVal]);

  const y = (v: number) => plotBottom - (v / niceMax) * (plotBottom - PAD_T);
  const band = (W - PAD_L - PAD_R) / slots.length;
  const barW = Math.max(8, Math.min(20, band - 12));

  const yTicks = [niceMax / 2, niceMax];
  const unit = UNIT_SHORT[market];
  const outCount = slots.length - ordered.length;
  const hovered = hover !== null ? slots[hover] : undefined;

  return (
    <div className="relative" ref={boxRef}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full select-none" role="img"
        aria-label={`Last ${ordered.length} games of ${unit}; bars above the ${fmtLine(line)} line are green, below are red${
          outCount > 0 ? `; ${outCount} hollow ${outCount === 1 ? "tick marks a week" : "ticks mark weeks"} with no game played` : ""
        }`}>
        {/* gridlines + y ticks */}
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={PAD_L} x2={W - PAD_R} y1={y(t)} y2={y(t)} stroke="rgba(148,163,184,0.13)" strokeWidth={1} />
            <text x={PAD_L - 6} y={y(t) + 3.5} textAnchor="end" fontSize={10} fill="#8792a6"
              style={{ fontVariantNumeric: "tabular-nums" }}>
              {fmtLine(t)}
            </text>
          </g>
        ))}
        <line x1={PAD_L} x2={W - PAD_R} y1={plotBottom} y2={plotBottom} stroke="rgba(148,163,184,0.3)" strokeWidth={1} />

        {/* bars + hollow "out" ticks */}
        {slots.map((s, i) => {
          const cx = PAD_L + band * i + band / 2;
          const isHover = hover === i;
          if (s.kind === "out") {
            return (
              <g key={`out-${s.season}-${s.week}`}>
                <circle
                  cx={cx}
                  cy={plotBottom - 7}
                  r={4.5}
                  fill="none"
                  stroke="#8792a6"
                  strokeWidth={1.5}
                  strokeDasharray="2.5 2"
                  opacity={isHover ? 1 : 0.7}
                />
                <text x={cx} y={plotBottom + 14} textAnchor="middle" fontSize={9.5} fill="#8792a6" opacity={0.65}>
                  W{s.week}
                </text>
                <rect
                  x={PAD_L + band * i}
                  y={PAD_T}
                  width={band}
                  height={plotBottom - PAD_T}
                  fill="transparent"
                  onPointerEnter={() => setHover(i)}
                  onPointerLeave={() => setHover(null)}
                  aria-label={`Week ${s.week}: no game played`}
                />
              </g>
            );
          }
          const g = s.g;
          const v = g.stats[market] ?? 0;
          const over = v > line;
          const h = Math.max(2, plotBottom - y(v));
          return (
            <g key={`${g.season}-${g.week}`}>
              <path
                d={`M ${cx - barW / 2} ${plotBottom}
                    L ${cx - barW / 2} ${plotBottom - h + 4}
                    Q ${cx - barW / 2} ${plotBottom - h} ${cx - barW / 2 + 4} ${plotBottom - h}
                    L ${cx + barW / 2 - 4} ${plotBottom - h}
                    Q ${cx + barW / 2} ${plotBottom - h} ${cx + barW / 2} ${plotBottom - h + 4}
                    L ${cx + barW / 2} ${plotBottom} Z`}
                fill={over ? "#0ea371" : "#e14d4d"}
                opacity={isHover ? 1 : 0.88}
              />
              <text x={cx} y={plotBottom + 14} textAnchor="middle" fontSize={9.5} fill="#8792a6">
                W{g.week}
              </text>
              {/* generous hit target */}
              <rect
                x={PAD_L + band * i}
                y={PAD_T}
                width={band}
                height={plotBottom - PAD_T}
                fill="transparent"
                onPointerEnter={() => setHover(i)}
                onPointerLeave={() => setHover(null)}
                aria-label={`Week ${g.week} ${g.home ? "vs" : "at"} ${g.opponent}: ${fmtStat(v)} ${unit}`}
              />
            </g>
          );
        })}

        {/* threshold line — the current slider line */}
        <line x1={PAD_L} x2={W - PAD_R + 6} y1={y(line)} y2={y(line)} stroke="#22d3ee" strokeWidth={1.5} strokeDasharray="6 4" />
        <text x={W - PAD_R + 10} y={y(line) + 3.5} fontSize={10.5} fontWeight={700} fill="#67e8f9"
          style={{ fontVariantNumeric: "tabular-nums" }}>
          line {fmtLine(line)}
        </text>
      </svg>

      {/* tooltip */}
      {hovered && hover !== null && (
        <div
          className="pointer-events-none absolute z-30 -translate-x-1/2 rounded-lg border border-edge bg-raised px-2.5 py-1.5 text-xs shadow-xl shadow-black/50"
          style={{
            left: `${((PAD_L + band * hover + band / 2) / W) * 100}%`,
            top: 0,
          }}
        >
          {hovered.kind === "out" ? (
            <>
              <span className="font-bold text-ink2">Out</span>
              <span className="ml-1.5 text-ink3">
                Wk {hovered.week} — no game (injury, rest, or bye)
              </span>
            </>
          ) : (
            <>
              <span className="tnum font-bold text-ink">
                {fmtStat(hovered.g.stats[market] ?? 0)} {unit}
              </span>
              <span className="ml-1.5 text-ink3">
                Wk {hovered.g.week} {hovered.g.home ? "vs" : "@"} {hovered.g.opponent}
              </span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
