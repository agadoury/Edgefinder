"use client";

import { useMemo, useState } from "react";
import type { CalibrationBucket, MarketId } from "../../lib/data";

/**
 * Calibration dot chart: what we predicted (x) vs what actually happened (y).
 * Dots hugging the diagonal = honest percentages.
 */
export function CalibrationChart({
  byMarket,
  labels,
}: {
  byMarket: Partial<Record<MarketId, CalibrationBucket[]>>;
  labels: Record<string, string>;
}) {
  const marketIds = useMemo(() => Object.keys(byMarket) as MarketId[], [byMarket]);
  const [active, setActive] = useState<MarketId>(marketIds[0]);
  const [hover, setHover] = useState<number | null>(null);

  const W = 380;
  const H = 330;
  const PAD_L = 46;
  const PAD_R = 16;
  const PAD_T = 16;
  const PAD_B = 44;
  const lo = 0.2;
  const hi = 0.8;
  const x = (p: number) => PAD_L + ((p - lo) / (hi - lo)) * (W - PAD_L - PAD_R);
  const y = (p: number) => H - PAD_B - ((p - lo) / (hi - lo)) * (H - PAD_T - PAD_B);
  const ticks = [0.3, 0.4, 0.5, 0.6, 0.7];

  const buckets = byMarket[active] ?? [];

  return (
    <div>
      {/* market tabs */}
      <div
        role="group"
        aria-label="Pick a market"
        className="mb-4 flex flex-wrap items-center gap-1 rounded-full border border-white/8 bg-white/3 p-1"
        style={{ width: "fit-content" }}
      >
        {marketIds.map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={active === m}
            onClick={() => {
              setActive(m);
              setHover(null);
            }}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
              active === m
                ? "accent-gradient text-white"
                : "text-ink2 hover:bg-white/6 hover:text-ink"
            }`}
          >
            {labels[m] ?? m}
          </button>
        ))}
      </div>

      <div className="relative" style={{ maxWidth: 420 }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full select-none"
          role="img"
          aria-label={`Calibration for ${labels[active]}: predicted chance versus how often it actually happened. Dots close to the diagonal mean honest percentages.`}
        >
          {/* grid */}
          {ticks.map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={PAD_T} y2={H - PAD_B} stroke="rgba(148,163,184,0.10)" />
              <line x1={PAD_L} x2={W - PAD_R} y1={y(t)} y2={y(t)} stroke="rgba(148,163,184,0.10)" />
              <text x={x(t)} y={H - PAD_B + 16} textAnchor="middle" fontSize={10} fill="#8792a6"
                style={{ fontVariantNumeric: "tabular-nums" }}>
                {Math.round(t * 100)}%
              </text>
              <text x={PAD_L - 8} y={y(t) + 3.5} textAnchor="end" fontSize={10} fill="#8792a6"
                style={{ fontVariantNumeric: "tabular-nums" }}>
                {Math.round(t * 100)}%
              </text>
            </g>
          ))}

          {/* perfect line */}
          <line x1={x(lo)} y1={y(lo)} x2={x(hi)} y2={y(hi)} stroke="rgba(148,163,184,0.45)" strokeWidth={1} />
          <text
            x={x(0.71)}
            y={y(0.735)}
            fontSize={9.5}
            fill="#8792a6"
            transform={`rotate(-38 ${x(0.71)} ${y(0.735)})`}
          >
            perfectly honest
          </text>

          {/* dots with surface ring */}
          {buckets.map((b, i) => (
            <g key={b.bucketMid}>
              <circle
                cx={x(b.predicted)}
                cy={y(b.actual)}
                r={6}
                fill="#6366f1"
                stroke="#0c1322"
                strokeWidth={2}
              />
              <circle
                cx={x(b.predicted)}
                cy={y(b.actual)}
                r={14}
                fill="transparent"
                onPointerEnter={() => setHover(i)}
                onPointerLeave={() => setHover(null)}
                aria-label={`Predicted ${Math.round(b.predicted * 100)}%, happened ${Math.round(
                  b.actual * 100
                )}% of the time, across ${b.n} calls`}
              />
            </g>
          ))}

          {/* axis titles */}
          <text x={(PAD_L + W - PAD_R) / 2} y={H - 8} textAnchor="middle" fontSize={11} fill="#9daebf" fontWeight={600}>
            what we predicted
          </text>
          <text
            x={12}
            y={(PAD_T + H - PAD_B) / 2}
            textAnchor="middle"
            fontSize={11}
            fill="#9daebf"
            fontWeight={600}
            transform={`rotate(-90 12 ${(PAD_T + H - PAD_B) / 2})`}
          >
            what actually happened
          </text>
        </svg>

        {hover !== null && buckets[hover] && (
          <div
            className="pointer-events-none absolute z-30 -translate-x-1/2 -translate-y-full rounded-lg border border-edge bg-raised px-2.5 py-1.5 text-xs whitespace-nowrap shadow-xl shadow-black/50"
            style={{
              left: `${(x(buckets[hover].predicted) / W) * 100}%`,
              top: `${(y(buckets[hover].actual) / H) * 100}%`,
            }}
          >
            <span className="tnum font-bold text-ink">
              said {Math.round(buckets[hover].predicted * 100)}% → happened{" "}
              {Math.round(buckets[hover].actual * 100)}%
            </span>
            <span className="tnum ml-1.5 text-ink3">({buckets[hover].n} calls)</span>
          </div>
        )}
      </div>
    </div>
  );
}
