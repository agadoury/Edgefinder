// Availability watch — derived server-side from exported data only.
//
// A player is flagged for a week when his TEAM verifiably played it (some
// teammate has a recentGames or modelHistory entry for that week) but he has
// no played game there himself. Bye weeks never flag (nobody on the team
// played); weeks outside a player's capped 10-game history are skipped as
// unknowable. This is a pre-kickoff schedule fact, never a result spoiler.
import { getPlayer, getPlayerIds, getSlate } from "./data";

/** How many weeks immediately before the demo week we scan. */
export const AVAILABILITY_WINDOW = 5;

let cache: Record<string, number[]> | null = null;

/** playerId -> weeks (ascending) the player missed while his team played,
 * within the last AVAILABILITY_WINDOW weeks before the demo week. Players
 * with no misses have no entry. */
export function getAvailabilityWatch(): Record<string, number[]> {
  if (cache) return cache;
  const slate = getSlate();
  const { season, week } = slate;
  const players = getPlayerIds().map(getPlayer);

  // Weeks each team verifiably played, from every teammate's exported rows.
  // modelHistory rows count even when the player was DNP — the game existed.
  const teamPlayed = new Map<string, Set<number>>();
  for (const p of players) {
    let set = teamPlayed.get(p.team);
    if (!set) teamPlayed.set(p.team, (set = new Set()));
    for (const g of p.recentGames) if (g.season === season) set.add(g.week);
    for (const h of p.modelHistory) set.add(h.week);
  }

  const out: Record<string, number[]> = {};
  for (const p of players) {
    const played = new Set(
      p.recentGames.filter((g) => g.season === season).map((g) => g.week)
    );
    for (const h of p.modelHistory) if (h.result !== "dnp") played.add(h.week);

    // recentGames is capped at the last 10 played — if all 10 slots are this
    // season, weeks before the oldest listed game are unknowable, not missed.
    const capFull =
      p.recentGames.length >= 10 && p.recentGames.every((g) => g.season === season);
    const floor = capFull ? Math.min(...p.recentGames.map((g) => g.week)) : 1;

    const teamWeeks = teamPlayed.get(p.team);
    const missed: number[] = [];
    for (let w = Math.max(1, week - AVAILABILITY_WINDOW); w < week; w++) {
      if (w < floor || played.has(w) || !teamWeeks?.has(w)) continue;
      missed.push(w);
    }
    if (missed.length > 0) out[p.playerId] = missed;
  }
  cache = out;
  return out;
}
