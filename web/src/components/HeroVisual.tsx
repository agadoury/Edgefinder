import { ArrowUp, Wind } from "lucide-react";

/**
 * Decorative product mock for the landing hero (lg+ only). Pure presentation —
 * numbers echo real Week 14 calls from the slate data, marked aria-hidden.
 * Front card: Jordan Love pass_yds (GB vs CHI) — proj 234.4 vs ref 193.5,
 * P(over) 75%. Back card: Ja'Marr Chase rec_yds in the 12 mph / 31°F
 * CIN @ BUF game — proj 73.0, lean UNDER 102.5.
 */
export function HeroVisual() {
  return (
    <div className="pointer-events-none relative hidden select-none lg:block" aria-hidden>
      {/* back card */}
      <div className="card absolute top-[300px] -right-5 z-0 w-64 rotate-3 border-white/10 bg-raised p-4 shadow-2xl shadow-black/40">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-push/25 bg-push/10">
            <Wind className="h-3.5 w-3.5 text-push" />
          </span>
          <p className="text-xs leading-snug font-semibold text-ink">
            12 mph wind, 31°F in Buffalo
          </p>
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-ink3">
          Cold and gusty caps the deep game. The model pegs Ja&apos;Marr at{" "}
          <span className="tnum font-bold text-ink2">73.0</span> receiving yards — lean{" "}
          <span className="font-bold text-under">UNDER 102.5</span>.
        </p>
      </div>

      {/* front card */}
      <div className="card relative z-10 w-80 -rotate-2 border-white/12 bg-surface p-4 shadow-2xl shadow-accentdeep/20">
        <div className="flex items-center gap-2.5">
          <span
            className="inline-flex h-8 w-8 items-center justify-center rounded-full text-[11px] font-bold text-white"
            style={{
              background: "linear-gradient(145deg, #203731, #203731dd)",
              boxShadow: "inset 0 0 0 2px #FFB61255, 0 0 0 1px rgba(255,255,255,0.1)",
            }}
          >
            JL
          </span>
          <div className="flex-1">
            <p className="text-sm leading-tight font-bold">Jordan Love</p>
            <p className="text-[11px] text-ink3">Passing Yards · CHI @ GB</p>
          </div>
          <span className="inline-flex items-center gap-1 rounded-full border border-over/25 bg-over/10 px-2 py-0.5 text-[10px] font-bold text-over">
            <ArrowUp className="h-2.5 w-2.5" strokeWidth={3} />
            OVER
          </span>
        </div>

        <svg viewBox="0 0 300 110" className="mt-3 w-full">
          <defs>
            <clipPath id="hv-over">
              <rect x={112} y={0} width={188} height={96} />
            </clipPath>
            <linearGradient id="hv-fade" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0ba5c0" stopOpacity="0.55" />
              <stop offset="100%" stopColor="#0ba5c0" stopOpacity="0.1" />
            </linearGradient>
          </defs>
          <path
            d="M 8 96 C 55 94, 80 18, 150 15 C 220 18, 245 94, 292 96 Z"
            fill="rgba(99,102,241,0.16)"
          />
          <path
            d="M 8 96 C 55 94, 80 18, 150 15 C 220 18, 245 94, 292 96 Z"
            fill="url(#hv-fade)"
            clipPath="url(#hv-over)"
          />
          <path
            d="M 8 96 C 55 94, 80 18, 150 15 C 220 18, 245 94, 292 96"
            fill="none"
            stroke="#818cf8"
            strokeWidth={2}
          />
          <line x1={112} x2={112} y1={8} y2={96} stroke="#22d3ee" strokeWidth={1.75} />
          <circle cx={112} cy={96} r={4.5} fill="#22d3ee" stroke="#0c1322" strokeWidth={2} />
          <line x1={8} x2={292} y1={96} y2={96} stroke="rgba(148,163,184,0.3)" strokeWidth={1} />
        </svg>

        <div className="mt-2 flex items-end justify-between">
          <div>
            <p className="text-[10px] tracking-wider text-ink3 uppercase">Projected</p>
            <p className="tnum text-xl leading-tight font-bold">
              234.4 <span className="text-xs font-medium text-ink3">yds</span>
            </p>
          </div>
          <div className="text-center">
            <p className="text-[10px] tracking-wider text-ink3 uppercase">Line</p>
            <p className="tnum text-sm font-bold text-accent2">193.5</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] tracking-wider text-ink3 uppercase">Clears it</p>
            <p className="tnum text-xl leading-tight font-bold text-over">75%</p>
          </div>
        </div>
      </div>
    </div>
  );
}
