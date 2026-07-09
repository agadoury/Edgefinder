"""Map slate players to ESPN headshot URLs.

The app hotlinks player portraits from ESPN's public headshot CDN
(https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png) and
falls back to team-colored monogram avatars whenever an image is missing
or fails to load. This script builds the playerId -> URL map by joining
the exported slate against the DynastyProcess player-ID crosswalk
(committed in-repo on GitHub, fetched like the rest of the raw data).

Join strategy: fantasy.nfl.com numeric ids do not appear in the
crosswalk, so players are matched on normalized name + position, with
team as the tiebreaker when two players share both. Unmatched players
simply keep their monogram avatar.

Usage:
    python3 pipeline/edgefinder/headshots.py \
        [--export-dir pipeline/data/export] [--out src/data/headshots.json]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from download import _fetch  # same cached fetcher as the rest of the raw data

ROOT = Path(__file__).resolve().parent.parent.parent
CROSSWALK_URL = (
    "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
)
CROSSWALK_PATH = ROOT / "pipeline" / "data" / "raw" / "db_playerids.csv"
ESPN_URL = "https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png"

SUFFIXES = re.compile(r"\s+(jr|sr|ii|iii|iv|v)\.?$", re.IGNORECASE)

# slate team codes are canonical nfldata codes; the crosswalk uses LAR-style
TEAM_ALIASES = {"LA": "LAR"}


# fantasy.nfl.com display name -> crosswalk merge_name, for nicknames the
# normalizer can't bridge
ALIASES = {"chig okonkwo": "chigoziem okonkwo"}


def merge_name(name: str) -> str:
    """Normalize a display name the way DynastyProcess builds merge_name
    (lowercase, periods/apostrophes stripped, hyphens kept, suffixes cut)."""
    n = name.lower().strip()
    n = re.sub(r"[.'’]", "", n)
    n = SUFFIXES.sub("", n)
    n = re.sub(r"\s+", " ", n).strip()
    return ALIASES.get(n, n)


def load_crosswalk() -> dict[tuple[str, str], list[dict]]:
    status = _fetch(CROSSWALK_URL, CROSSWALK_PATH)
    print(f"crosswalk: {status}", flush=True)
    by_key: dict[tuple[str, str], list[dict]] = {}
    with open(CROSSWALK_PATH, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("position") not in {"QB", "RB", "WR", "TE"}:
                continue
            espn = (row.get("espn_id") or "").strip()
            if not espn or espn == "NA":
                continue
            key = (row["merge_name"], row["position"])
            by_key.setdefault(key, []).append(row)
    return by_key


def build_map(export_dir: Path) -> tuple[dict[str, str], list[str]]:
    slate = json.loads((export_dir / "slate.json").read_text())
    players = {
        p["playerId"]: p
        for p in (
            {
                "playerId": r["playerId"],
                "name": r["name"],
                "pos": r["pos"],
                "team": r["team"],
            }
            for r in slate["props"]
        )
    }
    crosswalk = load_crosswalk()
    out: dict[str, str] = {}
    unmatched: list[str] = []
    for pid, p in players.items():
        candidates = crosswalk.get((merge_name(p["name"]), p["pos"]), [])
        if len(candidates) > 1:
            want = TEAM_ALIASES.get(p["team"], p["team"])
            narrowed = [c for c in candidates if c.get("team") == want]
            candidates = narrowed or candidates
        if candidates:
            out[pid] = ESPN_URL.format(espn_id=candidates[0]["espn_id"].strip())
        else:
            unmatched.append(f'{p["name"]} ({p["pos"]}, {p["team"]})')
    return out, unmatched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", type=Path, default=ROOT / "pipeline" / "data" / "export")
    parser.add_argument("--out", type=Path, default=ROOT / "src" / "data" / "headshots.json")
    args = parser.parse_args()

    mapping, unmatched = build_map(args.export_dir)
    args.out.write_text(json.dumps(mapping, indent=1, sort_keys=True) + "\n")
    total = len(mapping) + len(unmatched)
    print(f"headshots: {len(mapping)}/{total} players mapped -> {args.out}")
    if unmatched:
        print("unmatched (monogram fallback):")
        for u in unmatched:
            print(f"  - {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
