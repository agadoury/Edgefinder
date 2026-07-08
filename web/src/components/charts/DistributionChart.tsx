"use client";

import { useCallback, useId, useMemo, useRef } from "react";
import type { CurvePoint } from "../../lib/data";
import { snap } from "../../lib/prob";
import { fmtLine } from "../../lib/format";
import { useMeasuredWidth } from "./useMeasuredWidth";

/**
 * Hand-rolled SVG outcome curve built from the probCurve. The filled area is
 * the model's view of how the game could go; the region right of the draggable
 * line is shaded — that's P(over). Dragging anywhere on the chart moves the line.
 */
export function DistributionChart({
  curve,
  value,
  refLine,
  lineStep,
  onChange,
  actual,
  actualColor,
  showActual,
  ariaLabel,
}: {
  curve: CurvePoint[];
  value: number;
  refLine: number;
  lineStep: number;
  onChange: (v: number) => void;
  actual: number | null;
  actualColor: string;
  showActual: boolean;
  ariaLabel: string;
}) {
  const { ref: boxRef, width: W } = useMeasuredWidth<HTMLDivElement>(640);
  const H = W < 480 ? 170 : 200;
  const PAD_L = 10;
  const PAD_R = 10;
  const PAD_T = 26;
  const AXIS_H = 24;
  const plotBottom = H - AXIS_H;
  const svgRef = useRef<SVGSVGElement>(null);

  const lo = curve[0].line;
  const hi = curve[curve.length - 1].line;
  const x = useCallback(
    (line: number) => PAD_L + ((line - lo) / (hi - lo)) * (W - PAD_L - PAD_R),
    [lo, hi, W]
  );

  // density = negative slope of the P(over) curve, lightly smoothed
  const { areaPath, linePath, ticks } = useMemo(() => {
    const mids: { line: number; d: number }[] = [];
    for (let i = 0; i < curve.length - 1; i++) {
      const a = curve[i];
      const b = curve[i + 1];
      const dx = b.line - a.line;
      if (dx <= 0) continue;
      mids.push({ line: (a.line + b.line) / 2, d: (a.over - b.over) / dx });
    }
    // Gaussian-kernel smoothing: the exported curve is piecewise-linear
    // between quantile knots, so its raw derivative is a step function.
    // Cosmetic only — probability readouts interpolate the exact curve.
    const sigma = (hi - lo) / 14;
    const sm = mids.map((m) => {
      let num = 0;
      let den = 0;
      for (const o of mids) {
        const w = Math.exp(-((o.line - m.line) ** 2) / (2 * sigma * sigma));
        num += w * o.d;
        den += w;
      }
      return { line: m.line, d: den > 0 ? num / den : m.d };
    });
    const dMax = Math.max(...sm.map((m) => m.d), 1e-9);
    const pts = sm.map((m) => ({
      px: x(m.line),
      py: PAD_T + (1 - m.d / dMax) * (plotBottom - PAD_T),
    }));
    // pin the curve to the baseline at both ends
    const first = { px: x(lo), py: plotBottom };
    const last = { px: x(hi), py: plotBottom };
    const all = [first, ...pts, last];

    // Catmull-Rom → bezier for a smooth silhouette
    let d = `M ${all[0].px.toFixed(2)} ${all[0].py.toFixed(2)}`;
    for (let i = 0; i < all.length - 1; i++) {
      const p0 = all[Math.max(0, i - 1)];
      const p1 = all[i];
      const p2 = all[i + 1];
      const p3 = all[Math.min(all.length - 1, i + 2)];
      const c1x = p1.px + (p2.px - p0.px) / 6;
      const c1y = p1.py + (p2.py - p0.py) / 6;
      const c2x = p2.px - (p3.px - p1.px) / 6;
      const c2y = p2.py - (p3.py - p1.py) / 6;
      d += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(2)}, ${p2.px.toFixed(2)} ${p2.py.toFixed(2)}`;
    }
    const area = `${d} L ${x(hi).toFixed(2)} ${plotBottom} L ${x(lo).toFixed(2)} ${plotBottom} Z`;

    // clean x ticks
    const span = hi - lo;
    const rawStep = span / 5;
    const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= rawStep) ?? rawStep;
    const t: number[] = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) {
      t.push(Math.round(v * 100) / 100);
    }
    return { areaPath: area, linePath: d, ticks: t };
  }, [curve, lo, hi, x, plotBottom]);

  const sx = x(Math.min(hi, Math.max(lo, value)));
  const clipId = `over-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;

  const valueFromEvent = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      const svg = svgRef.current;
      if (!svg) return null;
      const rect = svg.getBoundingClientRect();
      const frac = (e.clientX - rect.left) / rect.width;
      const raw = lo + frac * (hi - lo);
      const snapped = snap(Math.min(hi, Math.max(lo, raw)), lineStep, refLine);
      return Math.min(hi, Math.max(lo, snapped));
    },
    [lo, hi, lineStep, refLine]
  );

  const dragging = useRef(false);

  return (
    <div ref={boxRef}>
    <svg
      ref={svgRef}
      viewBox={`0 0 ${W} ${H}`}
      className="w-full touch-none select-none"
      role="img"
      aria-label={ariaLabel}
      onPointerDown={(e) => {
        dragging.current = true;
        (e.target as Element).setPointerCapture?.(e.pointerId);
        const v = valueFromEvent(e);
        if (v !== null) onChange(v);
      }}
      onPointerMove={(e) => {
        if (!dragging.current) return;
        const v = valueFromEvent(e);
        if (v !== null) onChange(v);
      }}
      onPointerUp={() => {
        dragging.current = false;
      }}
      style={{ cursor: "ew-resize" }}
    >
      <defs>
        <linearGradient id={`${clipId}-fade`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0ba5c0" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#0ba5c0" stopOpacity="0.10" />
        </linearGradient>
        <clipPath id={clipId}>
          <rect x={sx} y={0} width={Math.max(0, W - PAD_R - sx)} height={plotBottom} />
        </clipPath>
      </defs>

      {/* baseline */}
      <line x1={PAD_L} x2={W - PAD_R} y1={plotBottom} y2={plotBottom} stroke="rgba(148,163,184,0.25)" strokeWidth={1} />
      {/* x ticks */}
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={plotBottom} y2={plotBottom + 4} stroke="rgba(148,163,184,0.4)" strokeWidth={1} />
          <text
            x={x(t)}
            y={plotBottom + 16}
            textAnchor="middle"
            fontSize={10.5}
            fill="#8792a6"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {fmtLine(t)}
          </text>
        </g>
      ))}

      {/* under-side wash */}
      <path d={areaPath} fill="rgba(99,102,241,0.14)" />
      {/* over-side shade (clipped) */}
      <path d={areaPath} fill={`url(#${clipId}-fade)`} clipPath={`url(#${clipId})`} />
      {/* silhouette */}
      <path d={linePath} fill="none" stroke="#818cf8" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

      {/* reference line marker */}
      <g aria-hidden>
        <line
          x1={x(refLine)}
          x2={x(refLine)}
          y1={plotBottom - 8}
          y2={plotBottom}
          stroke="#8792a6"
          strokeWidth={1.5}
        />
        <text x={x(refLine)} y={PAD_T - 14} textAnchor="middle" fontSize={0} fill="none">
          ref
        </text>
      </g>

      {/* actual outcome marker (revealed) */}
      {showActual && actual !== null && (
        <g aria-hidden={false} aria-label={`Actual result ${fmtLine(actual)}`}>
          <line
            x1={x(Math.min(hi, Math.max(lo, actual)))}
            x2={x(Math.min(hi, Math.max(lo, actual)))}
            y1={PAD_T - 4}
            y2={plotBottom}
            stroke={actualColor}
            strokeWidth={2}
            strokeDasharray="5 4"
          />
          <circle
            cx={x(Math.min(hi, Math.max(lo, actual)))}
            cy={PAD_T - 8}
            r={4.5}
            fill={actualColor}
            stroke="#0c1322"
            strokeWidth={2}
          />
          <text
            x={x(Math.min(hi, Math.max(lo, actual)))}
            y={PAD_T - 16}
            textAnchor="middle"
            fontSize={11}
            fontWeight={700}
            fill={actualColor}
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            actual {fmtLine(actual)}
          </text>
        </g>
      )}

      {/* draggable line */}
      <g aria-hidden>
        <line x1={sx} x2={sx} y1={PAD_T - 6} y2={plotBottom} stroke="#22d3ee" strokeWidth={1.75} />
        <circle cx={sx} cy={plotBottom} r={5} fill="#22d3ee" stroke="#0c1322" strokeWidth={2} />
        <rect x={sx - 14} y={0} width={28} height={plotBottom} fill="transparent" />
      </g>
    </svg>
    </div>
  );
}
