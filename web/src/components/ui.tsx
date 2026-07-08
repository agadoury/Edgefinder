// Shared presentational atoms — no hooks, safe in server and client components.
import type { Confidence, Lean, PropResult } from "../lib/data";
import { initials, monogramInk, team } from "../lib/teams";
import { fmtStat, leanLabel, resultLabel } from "../lib/format";
import { ArrowDown, ArrowUp, Check, Minus, X } from "lucide-react";

export function MonogramAvatar({
  name,
  teamCode,
  size = 36,
}: {
  name: string;
  teamCode: string;
  size?: number;
}) {
  const t = team(teamCode);
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold select-none"
      style={{
        width: size,
        height: size,
        background: `linear-gradient(145deg, ${t.primary}, ${t.primary}dd)`,
        color: monogramInk(t.primary),
        boxShadow: `inset 0 0 0 2px ${t.secondary}55, 0 0 0 1px rgba(255,255,255,0.10)`,
        fontSize: Math.max(10, Math.round(size * 0.34)),
        letterSpacing: "0.02em",
      }}
    >
      {initials(name)}
    </span>
  );
}

export function LeanPill({ lean, size = "md" }: { lean: Lean; size?: "sm" | "md" }) {
  const cls =
    lean === "over"
      ? "bg-over/10 text-over border-over/25"
      : lean === "under"
        ? "bg-under/10 text-under border-under/25"
        : "bg-white/5 text-ink2 border-white/10";
  const Icon = lean === "over" ? ArrowUp : lean === "under" ? ArrowDown : Minus;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-semibold tracking-wide ${cls} ${
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs"
      }`}
    >
      <Icon className={size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3"} aria-hidden strokeWidth={3} />
      {leanLabel(lean)}
    </span>
  );
}

/** 3-bar signal icon + label — level is encoded by bar count, not color alone. */
export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  const level = confidence === "high" ? 3 : confidence === "medium" ? 2 : 1;
  const label = confidence === "high" ? "High" : confidence === "medium" ? "Medium" : "Low";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ink2">
      <span className="flex items-end gap-[2.5px]" aria-hidden>
        {[1, 2, 3].map((i) => (
          <span
            key={i}
            className={`w-[3.5px] rounded-full ${i <= level ? "bg-accent" : "bg-white/12"}`}
            style={{ height: 4 + i * 3.5 }}
          />
        ))}
      </span>
      {label}
    </span>
  );
}

/** Meter: gradient fill on a same-ramp dim track. 0–100 = how hard the model leans. */
export function StrengthMeter({
  value,
  showValue = true,
  width = 72,
}: {
  value: number;
  showValue?: boolean;
  width?: number;
}) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        aria-label={`Lean strength ${value} out of 100`}
        className="relative inline-block h-1.5 overflow-hidden rounded-full bg-accentdeep/20"
        style={{ width }}
      >
        <span
          className="absolute inset-y-0 left-0 rounded-full accent-gradient"
          style={{ width: `${Math.max(3, value)}%` }}
        />
      </span>
      {showValue && <span className="tnum text-xs font-semibold text-ink2">{value}</span>}
    </span>
  );
}

export function ResultBadge({
  result,
  actual,
  unit,
}: {
  result: PropResult;
  actual: number | null;
  unit?: string;
}) {
  const cls =
    result === "over"
      ? "text-over"
      : result === "under"
        ? "text-under"
        : result === "push"
          ? "text-push"
          : "text-ink3";
  return (
    <span className={`inline-flex items-baseline gap-1.5 ${cls}`}>
      {actual !== null && (
        <span className="tnum text-sm font-bold">
          {fmtStat(actual)}
          {unit ? <span className="ml-0.5 text-[10px] font-medium opacity-80">{unit}</span> : null}
        </span>
      )}
      <span className="text-[10px] font-bold tracking-wider">{resultLabel(result)}</span>
    </span>
  );
}

/** Green tick / red cross for "did the model's lean hit?" — icon + color, never color alone. */
export function HitMissMark({
  outcome,
  size = 16,
}: {
  outcome: "hit" | "miss" | "push" | "dnp" | "nolean";
  size?: number;
}) {
  if (outcome === "hit")
    return (
      <span
        className="inline-flex items-center justify-center rounded-full bg-over/15 text-over"
        style={{ width: size + 6, height: size + 6 }}
        title="Model's lean hit"
        aria-label="Hit"
      >
        <Check style={{ width: size - 3, height: size - 3 }} strokeWidth={3.2} aria-hidden />
      </span>
    );
  if (outcome === "miss")
    return (
      <span
        className="inline-flex items-center justify-center rounded-full bg-under/15 text-under"
        style={{ width: size + 6, height: size + 6 }}
        title="Model's lean missed"
        aria-label="Miss"
      >
        <X style={{ width: size - 3, height: size - 3 }} strokeWidth={3.2} aria-hidden />
      </span>
    );
  return (
    <span
      className="inline-flex items-center justify-center rounded-full bg-white/6 text-ink3"
      style={{ width: size + 6, height: size + 6 }}
      title={outcome === "push" ? "Push — no winner" : outcome === "dnp" ? "Did not play" : "No lean"}
      aria-label={outcome === "push" ? "Push" : outcome === "dnp" ? "Did not play" : "No lean"}
    >
      <Minus style={{ width: size - 3, height: size - 3 }} strokeWidth={3} aria-hidden />
    </span>
  );
}
