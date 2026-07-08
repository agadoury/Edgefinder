import { Zap } from "lucide-react";

export function Footer({
  season,
  modelVersion,
}: {
  season: number;
  modelVersion: string;
}) {
  return (
    <footer className="mt-20 border-t border-white/7">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-md space-y-2">
            <div className="flex items-center gap-2">
              <span className="accent-gradient inline-flex h-6 w-6 items-center justify-center rounded-md">
                <Zap className="h-3.5 w-3.5 text-white" aria-hidden fill="currentColor" />
              </span>
              <span className="text-sm font-bold">EdgeFinder</span>
              <span className="chip">Replay mode: {season} season data</span>
            </div>
            <p className="text-xs leading-relaxed text-ink3">
              EdgeFinder analyzes player performance; it is not affiliated with any sportsbook and
              does not guarantee outcomes. Reference lines are our own — not betting lines. Model{" "}
              {modelVersion}.
            </p>
          </div>
          <div className="space-y-1.5 text-xs text-ink3 sm:text-right">
            <p className="font-semibold text-ink2">21+ only. Please play responsibly.</p>
            <p>
              Gambling problem? Call the problem gambling helpline:{" "}
              <a
                href="tel:1-800-426-2537"
                className="font-semibold text-ink2 underline decoration-white/25 underline-offset-2 hover:text-ink"
              >
                1-800-GAMBLER
              </a>
            </p>
            <p>Past accuracy never promises future results.</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
