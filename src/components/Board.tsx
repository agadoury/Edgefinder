"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, ArrowUpDown, EyeOff, Search, Star, X } from "lucide-react";
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
import { TIER_SCALE_COPY } from "../lib/tiers";
import { useWatchlist } from "../lib/store";
import { useReveal } from "./RevealContext";
import {
  AvailabilityDot,
  ConfidenceBadge,
  HitMissMark,
  LeanPill,
  ResultBadge,
  ResultTip,
  ResultsToggleName,
  StrengthMeter,
} from "./ui";
import { PlayerAvatar } from "./PlayerAvatar";
import { StarButton } from "./Star";
import { PickemBoardToggle } from "./Pickem";
import { InfoTip } from "./Tooltip";

type SortKey = "strength" | "name" | "market" | "confidence" | "pover";

const CONF_RANK = { high: 3, medium: 2, low: 1 } as const;
const LEAN_RANK = { over: 3, under: 2, neutral: 1 } as const;
const PAGE_SIZE = 30;
const SORT_KEYS: SortKey[] = ["strength", "pover", "confidence", "name", "market"];
const SORT_LABEL: Record<SortKey, string> = {
  strength: "Strength",
  pover: "P(over)",
  confidence: "Confidence",
  name: "Player",
  market: "Market",
};

/** Case-, punctuation- and accent-insensitive key: "A.J. Brown" -> "ajbrown". */
function searchKey(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "");
}

/** Swallow a click so tooltips inside row-links never navigate. */
function stopRowClick(e: React.MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
}

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
  tip?: { label: string; body: ReactNode };
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
              {(row.result === "dnp" || row.result === "push") && (
                <span onClick={stopRowClick} className="inline-flex">
                  <ResultTip result={row.result} />
                </span>
              )}
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

/** Delta and P(over) read in the LEAN's color, so the row never argues with itself. */
function leanTone(lean: SlateProp["lean"]): string {
  return lean === "over" ? "text-over" : lean === "under" ? "text-under" : "text-ink3";
}

const CONTRADICTION_TIP = {
  label: "Why can the projection sit on the other side of the line from the lean?",
  body: "The projection is the middle-of-the-road outcome; the lean comes from the whole range of outcomes. A lopsided range can put the middle on one side of the line while most outcomes still land on the other — trust the percentage.",
};

export function Board({
  rows,
  games,
  markets,
  headshots = {},
  availability = {},
}: {
  rows: SlateProp[];
  games: Game[];
  markets: MarketMeta[];
  headshots?: Record<string, string>;
  /** playerId -> recent weeks missed while the team played (availability watch). */
  availability?: Record<string, number[]>;
}) {
  const router = useRouter();
  const { revealed } = useReveal();
  const watchlist = useWatchlist();
  const [pos, setPos] = useState<string>("ALL");
  const [market, setMarket] = useState<string>("ALL");
  const [teamF, setTeamF] = useState<string>("ALL");
  const [leanF, setLeanF] = useState<string>("ALL");
  const [mine, setMine] = useState(false);
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("strength");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);
  // paging state resets whenever the filter combination changes
  const filterKey = `${pos}|${market}|${teamF}|${leanF}|${mine}|${searchKey(query)}`;
  const [paging, setPaging] = useState({ key: filterKey, n: PAGE_SIZE });
  const visible = paging.key === filterKey ? paging.n : PAGE_SIZE;
  const setVisible = (n: number) => setPaging({ key: filterKey, n });

  const teams = useMemo(() => [...new Set(rows.map((r) => r.team))].sort(), [rows]);
  const starredHere = useMemo(
    () => new Set(rows.filter((r) => watchlist.ids.includes(r.playerId)).map((r) => r.playerId))
      .size,
    [rows, watchlist.ids]
  );

  // ----- filter state <-> URL query params (shallow: no server round-trip) -----
  // Read once after hydration so a back-navigation (or a shared link) restores
  // the view. Deferred a tick (matching RevealContext) so the update never
  // cascades into the first render.
  const urlReady = useRef(false);
  useEffect(() => {
    const t = window.setTimeout(() => {
      const sp = new URLSearchParams(window.location.search);
      const pick = (key: string, ok: (v: string) => boolean): string | null => {
        const v = sp.get(key);
        return v !== null && ok(v) ? v : null;
      };
      const posV = pick("pos", (v) => ["QB", "RB", "WR", "TE"].includes(v));
      const marketV = pick("market", (v) => markets.some((m) => m.id === v));
      const teamV = pick("team", (v) => rows.some((r) => r.team === v));
      const leanV = pick("lean", (v) => v === "over" || v === "under");
      const sortV = pick("sort", (v) => (SORT_KEYS as string[]).includes(v));
      const dirV = pick("dir", (v) => v === "asc" || v === "desc");
      const qV = sp.get("q");
      if (posV) setPos(posV);
      if (marketV) setMarket(marketV);
      if (teamV) setTeamF(teamV);
      if (leanV) setLeanF(leanV);
      if (sp.get("mine") === "1") setMine(true);
      if (qV) setQuery(qV);
      if (sortV) setSortKey(sortV as SortKey);
      if (dirV) setSortDir(dirV === "asc" ? 1 : -1);
      urlReady.current = true;
    }, 0);
    return () => window.clearTimeout(t);
    // one-time URL read — rows/markets are static per page
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Mirror state into the URL. replaceState keeps history clean and shallow.
  useEffect(() => {
    if (!urlReady.current) return;
    const sp = new URLSearchParams(window.location.search);
    const put = (key: string, value: string, def: string) => {
      if (value === def) sp.delete(key);
      else sp.set(key, value);
    };
    put("pos", pos, "ALL");
    put("market", market, "ALL");
    put("team", teamF, "ALL");
    put("lean", leanF, "ALL");
    put("mine", mine ? "1" : "0", "0");
    put("q", query.trim(), "");
    put("sort", sortKey, "strength");
    put("dir", sortDir === 1 ? "asc" : "desc", "desc");
    const qs = sp.toString();
    const url = `${window.location.pathname}${qs ? `?${qs}` : ""}${window.location.hash}`;
    window.history.replaceState(window.history.state, "", url);
  }, [pos, market, teamF, leanF, mine, query, sortKey, sortDir]);

  const filtered = useMemo(() => {
    const q = searchKey(query);
    const out = rows.filter(
      (r) =>
        (pos === "ALL" || r.pos === pos) &&
        (market === "ALL" || r.market === market) &&
        (teamF === "ALL" || r.team === teamF) &&
        (leanF === "ALL" || r.lean === leanF) &&
        (!mine || watchlist.ids.includes(r.playerId)) &&
        (q === "" || searchKey(r.name).includes(q))
    );
    out.sort((a, b) => {
      let d = 0;
      if (sortKey === "strength") d = a.strength - b.strength;
      else if (sortKey === "pover") d = a.overProbAtRef - b.overProbAtRef;
      else if (sortKey === "name") d = a.name.localeCompare(b.name) * -1;
      else if (sortKey === "market") d = a.market.localeCompare(b.market) * -1;
      else if (sortKey === "confidence")
        d = CONF_RANK[a.confidence] - CONF_RANK[b.confidence] || a.strength - b.strength;
      if (d === 0) d = LEAN_RANK[a.lean] - LEAN_RANK[b.lean];
      if (d === 0) d = a.name.localeCompare(b.name) * -1;
      return d * sortDir;
    });
    return out;
  }, [rows, pos, market, teamF, leanF, mine, query, watchlist.ids, sortKey, sortDir]);

  const shown = filtered.slice(0, visible);
  const hiddenCount = filtered.length - shown.length;
  const filtersActive =
    pos !== "ALL" ||
    market !== "ALL" ||
    teamF !== "ALL" ||
    leanF !== "ALL" ||
    mine ||
    query.trim() !== "";

  const clearFilters = () => {
    setPos("ALL");
    setMarket("ALL");
    setTeamF("ALL");
    setLeanF("ALL");
    setMine(false);
    setQuery("");
  };

  // The record honors the active filters — it grades exactly the rows in view.
  const record = useMemo(() => {
    let hit = 0,
      miss = 0,
      push = 0,
      dnp = 0;
    for (const r of filtered) {
      const o = callOutcome(r.lean, r.result);
      if (o === "hit") hit++;
      else if (o === "miss") miss++;
      else if (o === "push") push++;
      else if (o === "dnp") dnp++;
    }
    return { hit, miss, push, dnp };
  }, [filtered]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 1 ? -1 : 1));
    else {
      setSortKey(key);
      setSortDir(-1);
    }
  };

  const rowMatchup = (r: SlateProp) => (r.home ? `vs ${r.opponent}` : `@ ${r.opponent}`);
  const th = { sortKey, sortDir, onSort: toggleSort };

  const emptyMessage =
    mine && watchlist.ids.length === 0 ? (
      <>
        <p className="font-medium text-ink2">No starred players yet.</p>
        <p className="mt-1">
          Tap the <Star className="inline h-3.5 w-3.5 align-[-2px]" aria-hidden /> next to any
          player to build your list — it sticks around in this browser.
        </p>
      </>
    ) : (
      <>
        <p>
          {query.trim() !== ""
            ? `No calls match “${query.trim()}” with these filters.`
            : "No calls match those filters."}
        </p>
        <button
          type="button"
          onClick={clearFilters}
          className="mt-3 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-semibold text-ink2 transition-colors hover:bg-white/10 hover:text-ink"
        >
          Clear filters
        </button>
      </>
    );

  return (
    <section aria-label="This week's top calls">
      {/* filter row */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {/* player search — full-width first thing on phones, compact on desktop */}
        <span className="relative order-first w-full sm:order-none sm:w-56">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2 text-ink3"
            aria-hidden
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search players…"
            aria-label="Search players by name"
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="search"
            className="h-8 w-full rounded-full border border-white/8 bg-white/3 pr-8 pl-8.5 text-xs font-medium text-ink placeholder:text-ink3 focus:border-accent2/50"
          />
          {query !== "" && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear player search"
              className="absolute top-1/2 right-1.5 inline-flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full text-ink3 transition-colors hover:bg-white/8 hover:text-ink"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          )}
        </span>
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
        <button
          type="button"
          aria-pressed={mine}
          onClick={() => setMine((v) => !v)}
          title="Only show players you starred"
          className={`inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-semibold transition-colors ${
            mine
              ? "border-push/40 bg-push/10 text-push"
              : "border-white/8 bg-white/3 text-ink2 hover:text-ink"
          }`}
        >
          <Star className="h-3.5 w-3.5" fill={mine ? "currentColor" : "none"} aria-hidden />
          My players{starredHere > 0 ? ` (${starredHere})` : ""}
        </button>
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
        {teams.length <= 3 ? (
          <FilterPills
            label="Filter by team"
            value={teamF}
            onChange={setTeamF}
            options={[
              { value: "ALL", label: "Both teams" },
              ...teams.map((t) => ({ value: t, label: t })),
            ]}
          />
        ) : (
          <>
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
          </>
        )}
        <PickemBoardToggle />

        {/* sort — the desktop table sorts via its headers; cards need their own control */}
        <span className="flex items-center gap-1 md:hidden">
          <label className="sr-only" htmlFor="mobile-sort">
            Sort calls by
          </label>
          <select
            id="mobile-sort"
            value={sortKey}
            onChange={(e) => {
              setSortKey(e.target.value as SortKey);
              setSortDir(-1);
            }}
            className="h-8 rounded-full border border-white/8 bg-white/3 px-3 text-xs font-semibold text-ink2 hover:text-ink"
          >
            {SORT_KEYS.map((k) => (
              <option key={k} value={k}>
                Sort: {SORT_LABEL[k]}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setSortDir((d) => (d === 1 ? -1 : 1))}
            aria-label={`Sort direction: ${sortDir === -1 ? "descending" : "ascending"} — tap to flip`}
            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/8 bg-white/3 text-ink2 transition-colors hover:text-ink"
          >
            {sortDir === -1 ? (
              <ArrowDown className="h-3.5 w-3.5 text-accent2" aria-hidden />
            ) : (
              <ArrowUp className="h-3.5 w-3.5 text-accent2" aria-hidden />
            )}
          </button>
        </span>

        <span className="ml-auto text-xs text-ink3">
          {revealed ? (
            <span className="fade-up inline-flex flex-wrap items-center gap-1.5 font-medium">
              {filtersActive && <span className="tnum">{filtered.length} in this view:</span>}
              <span className="text-over">{record.hit} hits</span>·
              <span className="text-under">{record.miss} misses</span>·
              <span className="inline-flex items-center gap-1">
                {record.push} push · {record.dnp} DNP
                <InfoTip label="What are pushes and DNPs?">
                  <strong className="text-ink">Push</strong> — the real number landed exactly on
                  the line. <strong className="text-ink">DNP</strong> — the player didn&apos;t
                  play. Neither gets a grade, so neither counts in the hit/miss record.
                </InfoTip>
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
                    body: "Our model's single best estimate for this stat in this exact matchup — shown against our reference line, with the gap colored by which side the model actually takes.",
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
                  label="P(over)"
                  k="pover"
                  tip={{
                    label: "What is P(over)?",
                    body: "The model's chance this player clears the reference line, from its full range of outcomes. 58% means 58 times in 100; below 50% favors the under.",
                  }}
                />
                <HeaderCell
                  {...th}
                  label="Strength"
                  k="strength"
                  tip={{
                    label: "What is strength?",
                    body: `How hard the model leans, 0–100, in plain words: ${TIER_SCALE_COPY}. It measures conviction versus our line — not value against a sportsbook.`,
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
                    body: (
                      <>
                        This is a replayed week, so real outcomes exist. Flip on{" "}
                        <ResultsToggleName /> in the header to check every call.
                      </>
                    ),
                  }}
                />
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => {
                const delta = r.projection - r.refLine;
                const contradicts =
                  (r.lean === "over" && delta < 0) || (r.lean === "under" && delta > 0);
                return (
                  <tr
                    key={`${r.playerId}-${r.market}`}
                    onClick={() => router.push(`/players/${r.playerId}`)}
                    className="group cursor-pointer border-b border-white/5 transition-colors last:border-0 hover:bg-white/3"
                  >
                    <td className="py-3 pr-3 pl-2">
                      <span className="flex items-center gap-1.5">
                        <StarButton playerId={r.playerId} name={r.name} size={15} />
                        <PlayerAvatar name={r.name} teamCode={r.team} size={34} src={headshots[r.playerId]} />
                        <span className="ml-1.5">
                          <span className="inline-flex items-center gap-1.5">
                            <Link
                              href={`/players/${r.playerId}`}
                              onClick={(e) => e.stopPropagation()}
                              className="font-semibold text-ink group-hover:text-accent group-hover:underline group-hover:decoration-accent/40 group-hover:underline-offset-4"
                            >
                              {r.name}
                            </Link>
                            {availability[r.playerId] && (
                              <span onClick={stopRowClick} className="inline-flex">
                                <AvailabilityDot
                                  name={r.name}
                                  missedWeeks={availability[r.playerId]}
                                />
                              </span>
                            )}
                          </span>
                          <span className="block text-xs text-ink3">
                            {r.pos} · {r.team} {rowMatchup(r)}
                          </span>
                        </span>
                      </span>
                    </td>
                    <td className="px-3 py-3 font-medium text-ink2">{MARKET_SHORT[r.market]}</td>
                    <td className="px-3 py-3">
                      <span className="flex items-center gap-1.5 whitespace-nowrap">
                        <span className="tnum text-[15px] font-bold">{fmtStat(r.projection)}</span>
                        <span className="tnum text-xs text-ink3">vs {fmtLine(r.refLine)}</span>
                        <span className={`tnum text-[11px] font-semibold ${leanTone(r.lean)}`}>
                          {fmtSigned(delta)}
                        </span>
                        {contradicts && (
                          <span onClick={(e) => e.stopPropagation()} className="inline-flex">
                            <InfoTip label={CONTRADICTION_TIP.label}>
                              {CONTRADICTION_TIP.body}
                            </InfoTip>
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <LeanPill lean={r.lean} size="sm" />
                    </td>
                    <td className="px-3 py-3">
                      <span className={`tnum text-sm font-semibold ${leanTone(r.lean)}`}>
                        {Math.round(r.overProbAtRef * 100)}%
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <StrengthMeter value={r.strength} width={56} />
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
                  <td colSpan={8} className="px-4 py-10 text-center text-sm text-ink3">
                    {emptyMessage}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* mobile cards */}
      <ul className="grid gap-3 md:hidden">
        {shown.map((r) => {
          const delta = r.projection - r.refLine;
          return (
            <li key={`${r.playerId}-${r.market}`}>
              <Link
                href={`/players/${r.playerId}`}
                className="card card-hover block p-4"
                aria-label={`${r.name} ${MARKET_SHORT[r.market]}, projected ${fmtStat(
                  r.projection
                )} versus line ${fmtLine(r.refLine)}, lean ${leanLabel(r.lean)}, ${Math.round(
                  r.overProbAtRef * 100
                )} percent to go over`}
              >
                <span className="flex items-center gap-2.5">
                  <PlayerAvatar name={r.name} teamCode={r.team} size={38} src={headshots[r.playerId]} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5">
                      <span className="truncate font-semibold">{r.name}</span>
                      {availability[r.playerId] && (
                        <span onClick={stopRowClick} className="inline-flex shrink-0">
                          <AvailabilityDot name={r.name} missedWeeks={availability[r.playerId]} />
                        </span>
                      )}
                    </span>
                    <span className="block text-xs text-ink3">
                      {r.pos} · {r.team} {rowMatchup(r)} · {MARKET_SHORT[r.market]}
                    </span>
                  </span>
                  <StarButton playerId={r.playerId} name={r.name} size={15} />
                  <LeanPill lean={r.lean} size="sm" />
                </span>
                <span className="mt-3 flex items-baseline justify-between gap-3">
                  <span className="flex items-baseline gap-1.5">
                    <span className="tnum text-lg font-bold">{fmtStat(r.projection)}</span>
                    <span className="tnum text-xs text-ink3">vs {fmtLine(r.refLine)}</span>
                    <span className={`tnum text-[11px] font-semibold ${leanTone(r.lean)}`}>
                      {fmtSigned(delta)}
                    </span>
                  </span>
                  <span className={`tnum text-xs font-semibold ${leanTone(r.lean)}`}>
                    {Math.round(r.overProbAtRef * 100)}%{" "}
                    <span className="font-medium text-ink3">over</span>
                  </span>
                </span>
                <span className="mt-2.5 flex items-center justify-between gap-3 border-t border-white/6 pt-2.5">
                  <StrengthMeter value={r.strength} width={48} />
                  <ConfidenceBadge confidence={r.confidence} />
                  <ResultCell row={r} />
                </span>
              </Link>
            </li>
          );
        })}
        {filtered.length === 0 && (
          <li className="card p-8 text-center text-sm text-ink3">{emptyMessage}</li>
        )}
      </ul>
      {hiddenCount > 0 && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => setVisible(visible + PAGE_SIZE)}
            className="rounded-full border border-white/10 bg-white/5 px-5 py-2.5 text-sm font-semibold text-ink2 transition-colors hover:bg-white/10 hover:text-ink"
          >
            Show {Math.min(PAGE_SIZE, hiddenCount)} more
          </button>
          <button
            type="button"
            onClick={() => setVisible(filtered.length)}
            className="rounded-full px-4 py-2.5 text-sm font-medium text-ink3 transition-colors hover:text-ink"
          >
            Show all {filtered.length}
          </button>
        </div>
      )}
      <p className="mt-3 text-xs text-ink3">
        {games.length} {games.length === 1 ? "game" : "games"} · {rows.length} calls · tap any row
        for the full breakdown
      </p>
    </section>
  );
}
