"use client";

// Pick 'em Before You Peek — call over/under yourself before the model shows
// its hand, then get graded side by side with it. Prediction practice, not a
// bet slip: the score is accuracy vs the model, never money, never streaks.
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import type { Lean, MarketId, PropResult } from "../lib/data";
import { usePickemOn, usePicks, type PickSide } from "../lib/store";

/** Compact per-prop index the provider needs to grade picks — no projections here. */
export interface PickemRow {
  playerId: string;
  market: MarketId;
  lean: Lean;
  result: PropResult;
}

export interface PickemRecord {
  /** Picks locked this week (graded or not). */
  locked: number;
  /** Picks with a decided over/under result. */
  graded: number;
  you: { wins: number; losses: number };
  /** The model's record on the same picked props (neutral leans get no grade). */
  model: { wins: number; losses: number };
}

interface PickemState {
  enabled: boolean;
  setEnabled: (v: boolean) => void;
  season: number;
  week: number;
  pickFor: (playerId: string, market: MarketId) => PickSide | undefined;
  lockPick: (playerId: string, market: MarketId, side: PickSide) => void;
  record: PickemRecord;
  /** Clear every pick for the current week. */
  resetWeek: () => void;
}

const EMPTY_RECORD: PickemRecord = {
  locked: 0,
  graded: 0,
  you: { wins: 0, losses: 0 },
  model: { wins: 0, losses: 0 },
};

const PickemCtx = createContext<PickemState>({
  enabled: false,
  setEnabled: () => {},
  season: 0,
  week: 0,
  pickFor: () => undefined,
  lockPick: () => {},
  record: EMPTY_RECORD,
  resetWeek: () => {},
});

export function PickemProvider({
  season,
  week,
  rows,
  children,
}: {
  season: number;
  week: number;
  rows: PickemRow[];
  children: ReactNode;
}) {
  const [enabled, setEnabled] = usePickemOn();
  const { picks, lock, clearPrefix } = usePicks();
  const prefix = `${season}.${week}.`;

  const rowIndex = useMemo(() => {
    const m = new Map<string, PickemRow>();
    for (const r of rows) m.set(`${r.playerId}.${r.market}`, r);
    return m;
  }, [rows]);

  const pickFor = useCallback(
    (playerId: string, market: MarketId) => picks[`${prefix}${playerId}.${market}`],
    [picks, prefix]
  );

  const lockPick = useCallback(
    (playerId: string, market: MarketId, side: PickSide) =>
      lock(`${prefix}${playerId}.${market}`, side),
    [lock, prefix]
  );

  const record = useMemo<PickemRecord>(() => {
    let locked = 0;
    let graded = 0;
    const you = { wins: 0, losses: 0 };
    const model = { wins: 0, losses: 0 };
    for (const [key, side] of Object.entries(picks)) {
      if (!key.startsWith(prefix)) continue;
      const row = rowIndex.get(key.slice(prefix.length));
      if (!row) continue;
      locked++;
      if (row.result !== "over" && row.result !== "under") continue; // push/DNP: no grade
      graded++;
      if (side === row.result) you.wins++;
      else you.losses++;
      if (row.lean !== "neutral") {
        if (row.lean === row.result) model.wins++;
        else model.losses++;
      }
    }
    return { locked, graded, you, model };
  }, [picks, prefix, rowIndex]);

  const resetWeek = useCallback(() => clearPrefix(prefix), [clearPrefix, prefix]);

  return (
    <PickemCtx.Provider
      value={{ enabled, setEnabled, season, week, pickFor, lockPick, record, resetWeek }}
    >
      {children}
    </PickemCtx.Provider>
  );
}

export function usePickem() {
  return useContext(PickemCtx);
}
