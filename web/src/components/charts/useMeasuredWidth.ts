"use client";

import { useEffect, useRef, useState } from "react";

/** Measure a container's width so SVG charts render at 1:1 pixel scale (crisp text at any viewport). */
export function useMeasuredWidth<T extends HTMLElement>(fallback = 640) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (!w || w <= 40) return;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => setWidth(w));
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      cancelAnimationFrame(raf);
    };
  }, []);
  return { ref, width };
}
