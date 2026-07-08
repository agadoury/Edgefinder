"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, ArrowUpDown, EyeOff } from "lucide-react";
import type { Game, MarketMeta, SlateProp } from "../lib/data";
import {
  MARKET_SHORT,
  UNIT_SHORT,
  callOutcome,
  fmtLine,
  fmtSigned,
  fmtStat,
  leanLabel,
} from "../lib/format";
import { useReveal } from "./RevealContext";
import {
  ConfidenceBadge,
  HitMissMark,
  LeanPill,
  MonogramAvatar,
  ResultBadge,
  StrengthMeter,
} from "./ui";
import { InfoTip } from "./Tooltip";

type SortKey = "strength" | "name" | "market" | "confidence";

const CONF_RANK = { high: 3, medium: 2, low: 1 } as const;
const LEAN_RANK = { over: 3, under: 2, neutral: 1 } as const;

function HeaderCell({
  label,
  k,
  className = "",
  tip,
  sortKey,
  sortDir,
  onSort,
}: {
  label: string;
  k?: SortKey;
  className?: string;
  tip?: { label: string; body: string };
  sortKey: SortKey;
  sortDir: 1 | -1;
  onSort: (k: SortKey) => void;
}) {
  return (
    <th scope="col" className={`px-3 py-2.5 text-left ${className}`}>
      <span className="inline-flex items-center gap-1">
        {k ? (
          <button
            type="button"
            onClick={() => onSort(k)}
            aria-label={`Sort by ${label}`}
            className="inline-flex items-center gap-1 text-[11px] font-semibold tracking-wider text-ink3 uppercase transition-colors hover:text-ink"
          >
            {label}
            {sortKey === k ? (
              sortDir === -1 ? (
                <ArrowDown className="h-3 w-3 text-accent2" aria-hidden />
              ) : (
                <ArrowUp className="h-3 w-3 text-accent2" aria-hidden />
              )
            ) : (
              <ArrowUpDown className="h-3 w-3 opacity-40" aria-hidden />
            )}
          </button>
        ) : (
          <span className="text-[11px] font-semibold tracking-wider text-ink3 uppercase">
            {label}
          </span>
        )}
        {tip && (
          <InfoTip label={tip.label} align="right">
            {tip.body}
          </InfoTip>
        )}
      </span>
    </th>
  );
}

function ResultCell({ row }: { row: SlateProp }) {
  const { revealed } = useReveal();
  const outcome = callOutcome(row.lean, row.result);
  return (
    <span className="flip-cell block" data-revealed={revealed}>
      <span className="flip-inner">
        <span className="flex h-8 items-center gap-1.5 text-ink3">
          <EyeOff className="h-3.5 w-3.5" aria-hidden />
          <span className="text-xs font-medium">Hidden</span>
        </span>
        <span className="flip-back flex h-8 items-center gap-2">
          {revealed && (
            <>
              <ResultBadge result={row.result} actual={row.actual} unit={UNIT_SHORT[row.market]} />
              <HitMissMark outcome={outcome} size={13} />
            </>
          )}
        </span>
      </span>
    </span>
  );
}

function FilterPills<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="flex items-center gap-1 rounded-full border border-white/8 bg-white/3 p-1"
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-full px-2.5 py-1 text-xs font-semibold transition-colors ${
            value === o.value
              ? "accent-gradient text-white shadow-sm"
              : "text-ink2 hover:bg-white/6 hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Board({
  rows,
  games,
  markets,
}: {
  rows: SlateProp[];
  games: Game[];
  markets: MarketMeta[];
}) {
  const router = useRouter();
  const { revealed } = useReveal();
  const [pos, setPos] = useState<string>("ALL");
  const [market, setMarket] = useState<string>("ALL");
  const [teamF, setTeamF] = useState<string>("ALL");
  const [leanF, setLeanF] = useState<string>("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("strength");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);

  const teams = useMemo(() => [...new Set(rows.map((r) => r.team))].sort(), [rows]);

  const filtered = useMemo(() => {
    const out = rows.filter(
      (r) =>
        (pos === "ALL" || r.pos === pos) &&
        (market === "ALL" || r.market === market) &&
        (teamF === "ALL" || r.team === teamF) &&
        (leanF === "ALL" || r.lean === leanF)
    );
    out.sort((a, b) => {
      let d = 0;
      if (sortKey === "strength") d = a.strength - b.strength;
      else if (sortKey === "name") d = a.name.localeCompare(b.name) * -1;
      else if (sortKey === "market") d = a.market.localeCompare(b.market) * -1;
      else if (sortKey === "confidence")
        d = CONF_RANK[a.confidence] - CONF_RANK[b.confidence] || a.strength - b.strength;
      if (d === 0) d = LEAN_RANK[a.lean] - LEAN_RANK[b.lean];
      if (d === 0) d = a.name.localeCompare(b.name) * -1;
      return d * sortDir;
    });
    return out;
  }, [rows, pos, market, teamF, leanF, sortKey, sortDir]);

  const record = useMemo(() => {
    let hit = 0,
      miss = 0,
      push = 0,
      dnp = 0;
    for (const r of rows) {
      const o = callOutcome(r.lean, r.result);
      if (o === "hit") hit++;
      else if (o === "miss") miss++;
      else if (o === "push") push++;
      else if (o === "dnp") dnp++;
    }
    return { hit, miss, push, dnp };
  }, [rows]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortKey(key);
      setSortDir(-1);
    }
  };

  const rowMatchup = (r: SlateProp) => (r.home ? `vs ${r.opponent}` : `@ ${r.opponent}`);
  const th = { sortKey, sortDir, onSort: toggleSort };

  return (
    <section id="board" aria-label="This week's top calls">
      {/* filter row */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <FilterPills
          label="Filter by position"
          value={pos}
          onChange={setPos}
          options={[
            { value: "ALL", label: "All" },
            { value: "QB", label: "QB" },
            { value: "RB", label: "RB" },
            { value: "WR", label: "WR" },
            { value: "TE", label: "TE" },
          ]}
        />
        <FilterPills
          label="Filter by lean"
          value={leanF}
          onChange={setLeanF}
          options={[
            { value: "ALL", label: "All leans" },
            { value: "over", label: "Over" },
            { value: "under", label: "Under" },
          ]}
        />
        <label className="sr-only" htmlFor="market-filter">
          Filter by market
        </label>
        <select
          id="market-filter"
          value={market}
          onChange={(e) => setMarket(e.target.value)}
          className="h-8 rounded-full border border-white/8 bg-white/3 px-3 text-xs font-semibold text-ink2 hover:text-ink"
        >
          <option value="ALL">All markets</option>
          {markets.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor="team-filter">
          Filter by team
        </label>
        <select
          id="team-filter"
          value={teamF}
          onChange={(e) => setTeamF(e.target.value)}
          className="h-8 rounded-full border border-white/8 bg-white/3 px-3 text-xs font-semibold text-ink2 hover:text-ink"
        >
          <option value="ALL">All teams</option>
          {teams.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <span className="ml-auto text-xs text-ink3">
          {revealed ? (
            <span className="fade-up inline-flex items-center gap-1.5 font-medium">
              <span className="text-over">{record.hit} hits</span>·
              <span className="text-under">{record.miss} misses</span>·
              <span>
                {record.push} push · {record.dnp} DNP
              </span>
            </span>
          ) : (
            `${filtered.length} of ${rows.length} calls`
          )}
        </span>
      </div>

      {/* desktop table */}
      <div className="card hidden overflow-hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-white/8 bg-white/2">
                <HeaderCell {...th} label="Player" k="name" className="pl-4" />
                <HeaderCell {...th} label="Market" k="market" />
                <HeaderCell
                  {...th}
                  label="Projection"
                  tip={{
                    label: "What is a projection?",
                    body: "Our model's single best estimate for this stat in this exact matchup — shown against our reference line.",
                  }}
                />
                <HeaderCell
                  {...th}
                  label="Lean"
                  tip={{
                    label: "What is a lean?",
                    body: "Which side of the reference line the model would take — over, under, or no lean when it's a coin flip.",
                  }}
                />
                <HeaderCell
                  {...th}
                  label="Strength"
                  k="strength"
                  tip={{
                    label: "What is strength?",
                    body: "How hard the model leans, 0–100. It measures conviction versus our line — not value against a sportsbook.",
                  }}
                />
                <HeaderCell
                  {...th}
                  label="Confidence"
                  k="confidence"
                  tip={{
                    label: "What is confidence?",
                    body: "How much trustworthy signal the model had — steady playing time and clean data raise it, injuries and small samples lower it.",
                  }}
                />
                <HeaderCell
                  {...th}
                  label="Result"
                  className="pr-4"
                  tip={{
                    label: "Why are results hidden?",
                    body: "This is a replayed week, so real outcomes exist. Flip on “Show results” in the header to check every call.",
                  }}
                />
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                const delta = r.projection - r.refLine;
                return (
                  <tr
                    key={`${r.playerId}-${r.market}`}
                    onClick={() => router.push(`/players/${r.playerId}`)}
                    className="group cursor-pointer border-b border-white/5 transition-colors last:border-0 hover:bg-white/3"
                  >
                    <td className="py-3 pr-3 pl-4">
                      <span className="flex items-center gap-3">
                        <MonogramAvatar name={r.name} teamCode={r.team} size={34} />
                        <span>
                          <Link
                            href={`/players/${r.playerId}`}
                            onClick={(e) => e.stopPropagation()}
                            className="font-semibold text-ink group-hover:text-accent group-hover:underline group-hover:decoration-accent/40 group-hover:underline-offset-4"
                          >
                            {r.name}
                          </Link>
                          <span className="block text-xs text-ink3">
                            {r.pos} · {r.team} {rowMatchup(r)}
                          </span>
                        </span>
                      </span>
                    </td>
                    <td className="px-3 py-3 font-medium text-ink2">{MARKET_SHORT[r.market]}</td>
                    <td className="px-3 py-3">
                      <span className="flex items-baseline gap-1.5">
                        <span className="tnum text-[15px] font-bold">{fmtStat(r.projection)}</span>
                        <span className="tnum text-xs text-ink3">vs {fmtLine(r.refLine)}</span>
                        <span
                          className={`tnum text-[11px] font-semibold ${
                            delta > 0 ? "text-over" : delta < 0 ? "text-under" : "text-ink3"
                          }`}
                        >
                          {fmtSigned(delta)}
                        </span>
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <LeanPill lean={r.lean} size="sm" />
                    </td>
                    <td className="px-3 py-3">
                      <StrengthMeter value={r.strength} />
                    </td>
                    <td className="px-3 py-3">
                      <ConfidenceBadge confidence={r.confidence} />
                    </td>
                    <td className="px-3 py-3 pr-4">
                      <ResultCell row={r} />
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-ink3">
                    No calls match those filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* mobile cards */}
      <ul className="grid gap-3 md:hidden">
        {filtered.map((r) => (
          <li key={`${r.playerId}-${r.market}`}>
            <Link
              href={`/players/${r.playerId}`}
              className="card card-hover block p-4"
              aria-label={`${r.name} ${MARKET_SHORT[r.market]}, projected ${fmtStat(
                r.projection
              )} versus line ${fmtLine(r.refLine)}, lean ${leanLabel(r.lean)}`}
            >
              <span className="flex items-center gap-3">
                <MonogramAvatar name={r.name} teamCode={r.team} size={38} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{r.name}</span>
                  <span className="block text-xs text-ink3">
                    {r.pos} · {r.team} {rowMatchup(r)} · {MARKET_SHORT[r.market]}
                  </span>
                </span>
                <LeanPill lean={r.lean} size="sm" />
              </span>
              <span className="mt-3 flex items-center justify-between gap-3">
                <span className="flex items-baseline gap-1.5">
                  <span className="tnum text-lg font-bold">{fmtStat(r.projection)}</span>
                  <span className="tnum text-xs text-ink3">vs {fmtLine(r.refLine)}</span>
                </span>
                <StrengthMeter value={r.strength} width={56} />
                <ResultCell row={r} />
              </span>
            </Link>
          </li>
        ))}
        {filtered.length === 0 && (
          <li className="card p-8 text-center text-sm text-ink3">No calls match those filters.</li>
        )}
      </ul>
      <p className="mt-3 text-xs text-ink3">
        {games.length} games · {rows.length} calls · tap any row for the full breakdown
      </p>
    </section>
  );
}
