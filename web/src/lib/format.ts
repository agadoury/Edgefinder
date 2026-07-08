// Client-safe formatting helpers and market copy.
import type { Game, Lean, MarketId, PropResult } from "./data";

export const MARKET_SHORT: Record<MarketId, string> = {
  pass_yds: "Pass Yds",
  pass_tds: "Pass TDs",
  rush_yds: "Rush Yds",
  rec_yds: "Rec Yds",
  receptions: "Receptions",
};

export const MARKET_LONG: Record<MarketId, string> = {
  pass_yds: "Passing Yards",
  pass_tds: "Passing TDs",
  rush_yds: "Rushing Yards",
  rec_yds: "Receiving Yards",
  receptions: "Receptions",
};

export const UNIT_SHORT: Record<MarketId, string> = {
  pass_yds: "yds",
  pass_tds: "TDs",
  rush_yds: "yds",
  rec_yds: "yds",
  receptions: "catches",
};

export const DISCRETE_MARKETS = new Set<MarketId>(["pass_tds", "receptions"]);

/** "261.4" for yards, "2.3" for TDs/receptions — always 1 decimal, matching the contract. */
export function fmtStat(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** A stat line value like 249.5 (always shows the half where present). */
export function fmtLine(value: number): string {
  return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1);
}

export function fmtPct(p: number): string {
  return `${Math.round(p * 100)}%`;
}

export function fmtSigned(value: number, decimals = 1): string {
  const s = value.toFixed(decimals);
  return value > 0 ? `+${s}` : s;
}

export function fmtKickoff(iso: string): string {
  const d = new Date(iso);
  const day = new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  }).format(d);
  const time = new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
  }).format(d);
  return `${day} · ${time} ET`;
}

export function fmtKickoffTime(iso: string): string {
  const d = new Date(iso);
  return `${new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
  }).format(d)} ET`;
}

/** "BUF −2.5" — whichever side is favored; "Pick'em" at 0. */
export function fmtSpread(game: Game): string {
  if (game.homeSpread === 0) return "Pick'em";
  const favored = game.homeSpread < 0 ? game.home : game.away;
  const points = Math.abs(game.homeSpread);
  return `${favored} −${fmtLine(points)}`;
}

export function leanLabel(lean: Lean): string {
  return lean === "over" ? "OVER" : lean === "under" ? "UNDER" : "NO LEAN";
}

export function resultLabel(result: PropResult): string {
  return result === "dnp" ? "DNP" : result.toUpperCase();
}

/** Did the model's lean hit? Only meaningful for decided, leaned calls. */
export function callOutcome(
  lean: Lean,
  result: PropResult
): "hit" | "miss" | "push" | "dnp" | "nolean" {
  if (result === "dnp") return "dnp";
  if (result === "push") return "push";
  if (lean === "neutral") return "nolean";
  return lean === result ? "hit" : "miss";
}

export function firstName(name: string): string {
  return name.split(" ")[0];
}
