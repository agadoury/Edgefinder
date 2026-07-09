"use client";

// Tiny localStorage-backed external stores. No accounts, no backend — a
// starred player or a locked pick lives in this browser only. Every store
// degrades gracefully when localStorage is unavailable (private mode, etc.).
import { useCallback, useSyncExternalStore } from "react";

class LocalStore<T> {
  private value: T;
  private loaded = false;
  private listeners = new Set<() => void>();

  constructor(
    private key: string,
    private fallback: T
  ) {
    this.value = fallback;
  }

  private load() {
    if (this.loaded || typeof window === "undefined") return;
    this.loaded = true;
    try {
      const raw = window.localStorage.getItem(this.key);
      if (raw !== null) this.value = JSON.parse(raw) as T;
    } catch {
      // corrupted or unavailable — keep the fallback
    }
  }

  // Stable references so useSyncExternalStore doesn't loop.
  getSnapshot = (): T => {
    this.load();
    return this.value;
  };

  getServerSnapshot = (): T => this.fallback;

  set = (next: T) => {
    this.loaded = true;
    this.value = next;
    try {
      window.localStorage.setItem(this.key, JSON.stringify(next));
    } catch {
      // storage full/unavailable — state still works for this visit
    }
    this.listeners.forEach((l) => l());
  };

  subscribe = (l: () => void) => {
    this.listeners.add(l);
    return () => {
      this.listeners.delete(l);
    };
  };
}

function useStore<T>(store: LocalStore<T>): T {
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot);
}

// ---------- My Players watchlist ----------

const watchlistStore = new LocalStore<string[]>("edgefinder.watchlist", []);

export function useWatchlist(): {
  ids: string[];
  has: (playerId: string) => boolean;
  toggle: (playerId: string) => void;
} {
  const ids = useStore(watchlistStore);
  const has = useCallback((playerId: string) => ids.includes(playerId), [ids]);
  const toggle = useCallback(
    (playerId: string) => {
      const cur = watchlistStore.getSnapshot();
      watchlistStore.set(
        cur.includes(playerId) ? cur.filter((id) => id !== playerId) : [...cur, playerId]
      );
    },
    []
  );
  return { ids, has, toggle };
}

// ---------- Pick 'em Before You Peek ----------

export type PickSide = "over" | "under";

const pickemOnStore = new LocalStore<boolean>("edgefinder.pickem.on", false);
// Keyed `${season}.${week}.${playerId}.${market}` — live-season ready.
const picksStore = new LocalStore<Record<string, PickSide>>("edgefinder.pickem.picks", {});

export function usePickemOn(): [boolean, (v: boolean) => void] {
  const on = useStore(pickemOnStore);
  const setOn = useCallback((v: boolean) => pickemOnStore.set(v), []);
  return [on, setOn];
}

export function usePicks(): {
  picks: Record<string, PickSide>;
  lock: (key: string, side: PickSide) => void;
  clearPrefix: (prefix: string) => void;
} {
  const picks = useStore(picksStore);
  const lock = useCallback((key: string, side: PickSide) => {
    const cur = picksStore.getSnapshot();
    if (cur[key]) return; // picks are locked — no take-backs after peeking
    picksStore.set({ ...cur, [key]: side });
  }, []);
  const clearPrefix = useCallback((prefix: string) => {
    const cur = picksStore.getSnapshot();
    const next: Record<string, PickSide> = {};
    for (const [k, v] of Object.entries(cur)) {
      if (!k.startsWith(prefix)) next[k] = v;
    }
    picksStore.set(next);
  }, []);
  return { picks, lock, clearPrefix };
}
