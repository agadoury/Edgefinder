// EdgeFinder data layer — the ONLY reader of web/src/data/.
// Interfaces mirror docs/DATA_CONTRACT.md exactly. Server-side only (uses fs).
import fs from "node:fs";
import path from "node:path";

// ---------- contract types ----------

export type MarketId =
  | "pass_yds"
  | "pass_tds"
  | "rush_yds"
  | "rec_yds"
  | "receptions";

export type Roof = "outdoors" | "dome" | "closed" | "open";
export type Lean = "over" | "under" | "neutral";
export type Confidence = "high" | "medium" | "low";
export type PropResult = "over" | "under" | "push" | "dnp";
export type Direction = "up" | "down";

export type FactorGroup =
  | "recent_form"
  | "usage_role"
  | "opp_defense"
  | "game_environment"
  | "weather"
  | "rest_schedule"
  | "qb_situation"
  | "home_away";

export interface MarketMeta {
  id: MarketId;
  label: string;
  unit: string;
  positions: string[];
  lineStep: number;
}

export interface CalibrationBucket {
  bucketMid: number;
  predicted: number;
  actual: number;
  n: number;
}

export interface MarketBacktest {
  n: number;
  mae: number;
  baselineMae: number;
  coverage80: number;
  strongCallHitRate: number;
  strongCallN: number;
  calibration: CalibrationBucket[];
}

export interface Backtest {
  season: number;
  weeksEvaluated: number;
  byMarket: Partial<Record<MarketId, MarketBacktest>>;
}

export interface Meta {
  generatedAt: string;
  season: number;
  week: number;
  mode: string;
  modelVersion: string;
  trainSeasons: number[];
  markets: MarketMeta[];
  backtest: Backtest;
}

export interface Game {
  gameId: string;
  away: string;
  home: string;
  kickoff: string;
  roof: Roof;
  surface: string;
  tempF: number | null;
  windMph: number | null;
  vegasTotal: number;
  homeSpread: number;
  stadium: string;
  awayQb: string;
  homeQb: string;
}

export interface SlateProp {
  playerId: string;
  name: string;
  team: string;
  pos: string;
  opponent: string;
  home: boolean;
  gameId: string;
  market: MarketId;
  projection: number;
  refLine: number;
  overProbAtRef: number;
  lean: Lean;
  strength: number;
  confidence: Confidence;
  actual: number | null;
  result: PropResult;
}

export interface Slate {
  season: number;
  week: number;
  games: Game[];
  props: SlateProp[];
}

export interface Quantiles {
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
}

export interface CurvePoint {
  line: number;
  over: number;
}

export interface Factor {
  group: FactorGroup;
  direction: Direction;
  impact: number;
  label: string;
  detail: string;
}

export interface PlayerProp {
  market: MarketId;
  projection: number;
  quantiles: Quantiles;
  probCurve: CurvePoint[];
  refLine: number;
  overProbAtRef: number;
  lean: Lean;
  strength: number;
  confidence: Confidence;
  confidenceReason: string;
  verdict: string;
  factors: Factor[];
  actual: number | null;
  result: PropResult;
}

export interface RecentGame {
  season: number;
  week: number;
  opponent: string;
  home: boolean;
  stats: Record<MarketId, number>;
}

export interface HistoryCall {
  week: number;
  market: MarketId;
  projection: number;
  refLine: number;
  lean: Lean;
  actual: number;
  result: PropResult;
}

export interface PlayerFile {
  playerId: string;
  name: string;
  team: string;
  pos: string;
  opponent: string;
  home: boolean;
  gameId: string;
  gamesPlayed2025: number;
  props: PlayerProp[];
  recentGames: RecentGame[];
  seasonAvgs: Partial<Record<MarketId, number>>;
  modelHistory: HistoryCall[];
}

// ---------- loaders ----------

const DATA_DIR = path.join(process.cwd(), "src", "data");

function readJson<T>(...segments: string[]): T {
  const raw = fs.readFileSync(path.join(DATA_DIR, ...segments), "utf-8");
  return JSON.parse(raw) as T;
}

let metaCache: Meta | null = null;
let slateCache: Slate | null = null;
const playerCache = new Map<string, PlayerFile>();

export function getMeta(): Meta {
  if (!metaCache) metaCache = readJson<Meta>("meta.json");
  return metaCache;
}

export function getSlate(): Slate {
  if (!slateCache) slateCache = readJson<Slate>("slate.json");
  return slateCache;
}

export function getPlayerIds(): string[] {
  return fs
    .readdirSync(path.join(DATA_DIR, "players"))
    .filter((f) => f.endsWith(".json"))
    .map((f) => f.replace(/\.json$/, ""));
}

export function getPlayer(playerId: string): PlayerFile {
  const cached = playerCache.get(playerId);
  if (cached) return cached;
  const file = readJson<PlayerFile>("players", `${playerId}.json`);
  playerCache.set(playerId, file);
  return file;
}

let headshotsCache: Record<string, string> | null = null;

/** Optional playerId -> portrait URL map (headshots.json). Players without
 * an entry — or whose image fails to load — fall back to monogram avatars. */
export function getHeadshots(): Record<string, string> {
  if (!headshotsCache) {
    try {
      headshotsCache = readJson<Record<string, string>>("headshots.json");
    } catch {
      headshotsCache = {};
    }
  }
  return headshotsCache;
}

export function getGame(gameId: string): Game {
  const game = getSlate().games.find((g) => g.gameId === gameId);
  if (!game) throw new Error(`Unknown gameId: ${gameId}`);
  return game;
}

export function getMarketMeta(id: MarketId): MarketMeta {
  const m = getMeta().markets.find((mk) => mk.id === id);
  if (!m) throw new Error(`Unknown market: ${id}`);
  return m;
}
