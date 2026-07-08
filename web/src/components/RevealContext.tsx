"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

const STORAGE_KEY = "edgefinder.showResults";

interface RevealState {
  revealed: boolean;
  toggle: () => void;
  setRevealed: (v: boolean) => void;
}

const RevealCtx = createContext<RevealState>({
  revealed: false,
  toggle: () => {},
  setRevealed: () => {},
});

export function RevealProvider({ children }: { children: ReactNode }) {
  const [revealed, setRevealedState] = useState(false);

  useEffect(() => {
    // Deferred so the post-hydration update never cascades into the first render.
    const t = window.setTimeout(() => {
      try {
        if (window.localStorage.getItem(STORAGE_KEY) === "1") setRevealedState(true);
      } catch {
        // localStorage unavailable — default stays off
      }
    }, 0);
    return () => window.clearTimeout(t);
  }, []);

  const setRevealed = useCallback((v: boolean) => {
    setRevealedState(v);
    try {
      window.localStorage.setItem(STORAGE_KEY, v ? "1" : "0");
    } catch {
      // ignore
    }
  }, []);

  const toggle = useCallback(() => setRevealed(!revealed), [revealed, setRevealed]);

  return (
    <RevealCtx.Provider value={{ revealed, toggle, setRevealed }}>{children}</RevealCtx.Provider>
  );
}

export function useReveal() {
  return useContext(RevealCtx);
}
