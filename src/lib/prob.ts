// Client-safe probability helpers. Implements the contract's frontend
// interpolation rule exactly: linear interpolation on probCurve between the
// two bracketing points; clamp to the curve's end values outside its range.
import type { CurvePoint } from "./data";

export function probOver(curve: CurvePoint[], line: number): number {
  if (curve.length === 0) return 0.5;
  if (line <= curve[0].line) return curve[0].over;
  const last = curve[curve.length - 1];
  if (line >= last.line) return last.over;
  for (let i = 0; i < curve.length - 1; i++) {
    const a = curve[i];
    const b = curve[i + 1];
    if (line >= a.line && line <= b.line) {
      if (b.line === a.line) return a.over;
      const t = (line - a.line) / (b.line - a.line);
      return a.over + t * (b.over - a.over);
    }
  }
  return last.over;
}

/**
 * The model's fair line: where P(over) crosses 50%, linearly interpolated
 * between the two bracketing probCurve points. When the whole curve sits on
 * one side of 50/50 (shouldn't happen for exported props), clamp to the
 * nearer end of the curve.
 */
export function fairLine(curve: CurvePoint[]): number | null {
  if (curve.length === 0) return null;
  if (curve[0].over <= 0.5) return curve[0].line;
  const last = curve[curve.length - 1];
  if (last.over >= 0.5) return last.line;
  for (let i = 0; i < curve.length - 1; i++) {
    const a = curve[i];
    const b = curve[i + 1];
    if (a.over >= 0.5 && b.over <= 0.5) {
      if (a.over === b.over) return (a.line + b.line) / 2;
      const t = (a.over - 0.5) / (a.over - b.over);
      return a.line + t * (b.line - a.line);
    }
  }
  return null;
}

/** Round away floating-point fuzz from repeated step arithmetic. */
export function snap(value: number, step: number, anchor: number): number {
  const n = Math.round((value - anchor) / step);
  return Math.round((anchor + n * step) * 100) / 100;
}

/**
 * Slider domain: values of the form refLine + k*lineStep that stay inside the
 * probCurve's range, so the slider always snaps to lineStep and starts at refLine.
 */
export function sliderDomain(
  curve: CurvePoint[],
  refLine: number,
  step: number
): { min: number; max: number } {
  const lo = curve[0].line;
  const hi = curve[curve.length - 1].line;
  const down = Math.floor((refLine - lo) / step + 1e-9);
  const up = Math.floor((hi - refLine) / step + 1e-9);
  return {
    min: snap(refLine - down * step, step, refLine),
    max: snap(refLine + up * step, step, refLine),
  };
}
