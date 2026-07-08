"use client";

import { useEffect, useRef, useState } from "react";

/** Animated count-up number. Respects prefers-reduced-motion (renders instantly). */
export function CountUp({
  value,
  decimals = 1,
  duration = 900,
  className,
}: {
  value: number;
  decimals?: number;
  duration?: number;
  className?: string;
}) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      const raf = requestAnimationFrame(() => setDisplay(value));
      return () => cancelAnimationFrame(raf);
    }
    const start = (animate: boolean) => {
      if (started.current) return;
      started.current = true;
      if (!animate) {
        setDisplay(value);
        return;
      }
      const t0 = performance.now();
      const tick = (t: number) => {
        const p = Math.min(1, (t - t0) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        setDisplay(value * eased);
        if (p < 1) requestAnimationFrame(tick);
        else setDisplay(value);
      };
      requestAnimationFrame(tick);
    };
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        start(true);
        io.disconnect();
      },
      { threshold: 0.4 }
    );
    io.observe(el);
    // Below-the-fold safety net: never leave the number at 0.
    const fallback = window.setTimeout(() => start(false), 700);
    return () => {
      io.disconnect();
      window.clearTimeout(fallback);
    };
  }, [value, duration]);

  return (
    <span ref={ref} className={className} aria-label={value.toFixed(decimals)}>
      {display.toFixed(decimals)}
    </span>
  );
}
