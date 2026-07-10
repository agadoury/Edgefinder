"""Fetch the enrichment datasets consumed by the M9/M10 features + M13 benchmark.

Datasets (all free, public), cached under pipeline/data/raw/enrichment/:

- snap_counts/snap_counts_{season}.csv.gz   — nflverse snap counts
  (offense_snaps / offense_pct per player-game)
- injuries/injuries_{season}.csv.gz          — nflverse official injury
  reports (report_status Out/Doubtful/Questionable + practice participation)
- player_stats/stats_player_week_{season}.csv — nflverse stats_player_week
  (air yards, target_share, air_yards_share, wopr, racr, ...)
- props/fanduel_*_history.csv                — archived FanDuel player-prop
  line snapshots (pass yds + receptions), Sep 2023 - Jan 2026. Evaluation
  only (M13); never a model input.

Sources, in preference order:

1. CANONICAL — nflverse-data GitHub release assets. Authoritative and
   refreshed upstream, but release downloads redirect through github.com,
   which some sandboxed build environments block.
2. MIRRORS — plain raw.githubusercontent.com copies of the same files,
   PINNED to a specific commit so the bytes cannot change under us.

   MIRROR RISK: these are personal repos (dachhack/stathead,
   Oliverwkw/LOTG-Stats, firstandthirty/nfl-tools), not nflverse
   infrastructure. A pinned commit protects against history rewrites and
   silent content drift, but not against the repo being deleted or made
   private — treat mirrors as a fallback of convenience, verify row counts
   and schemas after any refresh, and prefer the canonical release URL
   whenever the network allows. `refresh_mirror_pin()` below re-resolves a
   mirror's HEAD over git smart-HTTP (which typically works even where the
   github.com website/API is blocked) so pins can be advanced deliberately,
   never implicitly.

Usage:
    python3 pipeline/edgefinder/enrich.py           # fetch into the raw cache
    python3 pipeline/edgefinder/enrich.py --report  # availability report only
    python3 pipeline/edgefinder/enrich.py --refresh-pins  # show current HEADs
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ""):  # script mode: python3 pipeline/edgefinder/enrich.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from edgefinder.download import RAW_DIR, SEASONS, _fetch

ENRICH_DIR_NAME = "enrichment"

RELEASE_BASE = "https://github.com/nflverse/nflverse-data/releases/download"
RAW_GH = "https://raw.githubusercontent.com"

#: pinned mirror commits (see MIRROR RISK above; refresh deliberately via
#: refresh_mirror_pin, then re-verify schemas before committing a new pin)
MIRROR_PINS = {
    "dachhack/stathead": "ff229ec3fa54ea25b0ff62ec0ff944321f70e4af",
    # resolved from HEAD via refresh_mirror_pin and byte-verified against
    # the cached files (md5 match) before pinning
    "Oliverwkw/LOTG-Stats": "b7d1cd0b972dcb821432be326a21fe654756b960",
    "firstandthirty/nfl-tools": "9d6bdecbb00e5b4d5473f1b37ff669d74e849bb9",
}


@dataclass(frozen=True)
class Dataset:
    """One enrichment dataset: local layout + source URLs in fetch order."""

    name: str                       # cache subdir under raw/enrichment/
    filename: str                   # local file name ({season} substituted)
    canonical: str | None           # preferred URL template, None = mirror-only
    mirrors: tuple[str, ...] = ()   # pinned fallback URL templates
    per_season: bool = True         # False = single file, no {season}

    def urls(self, season: int | None = None) -> list[str]:
        """Candidate URLs, canonical first, then pinned mirrors."""
        templates = ([self.canonical] if self.canonical else []) + list(self.mirrors)
        return [t.format(season=season) for t in templates]

    def dest(self, raw_dir: Path, season: int | None = None) -> Path:
        return (raw_dir / ENRICH_DIR_NAME / self.name
                / self.filename.format(season=season))


DATASETS: dict[str, Dataset] = {
    "snap_counts": Dataset(
        name="snap_counts",
        filename="snap_counts_{season}.csv.gz",
        canonical=f"{RELEASE_BASE}/snap_counts/snap_counts_{{season}}.csv.gz",
        mirrors=(
            f"{RAW_GH}/dachhack/stathead/{MIRROR_PINS['dachhack/stathead']}"
            "/public/data/snap_counts_{season}.csv.gz",
        ),
    ),
    "injuries": Dataset(
        name="injuries",
        filename="injuries_{season}.csv.gz",
        canonical=f"{RELEASE_BASE}/injuries/injuries_{{season}}.csv.gz",
        mirrors=(
            f"{RAW_GH}/dachhack/stathead/{MIRROR_PINS['dachhack/stathead']}"
            "/public/data/injuries_{season}.csv.gz",
        ),
    ),
    "player_stats": Dataset(
        name="player_stats",
        filename="stats_player_week_{season}.csv",
        canonical=f"{RELEASE_BASE}/player_stats/stats_player_week_{{season}}.csv",
        mirrors=(
            f"{RAW_GH}/Oliverwkw/LOTG-Stats/{MIRROR_PINS['Oliverwkw/LOTG-Stats']}"
            "/.cache/nflverse_stats_player_week_{season}.csv",
        ),
    ),
    "props_pass_yds": Dataset(
        name="props",
        filename="fanduel_pass_yds_history.csv",
        canonical=None,  # archived line snapshots exist only on the mirror
        mirrors=(
            f"{RAW_GH}/firstandthirty/nfl-tools/"
            f"{MIRROR_PINS['firstandthirty/nfl-tools']}"
            "/player_props/data/processed/fanduel_pass_yds_history.csv",
        ),
        per_season=False,
    ),
    "props_receptions": Dataset(
        name="props",
        filename="fanduel_receptions_history.csv",
        canonical=None,
        mirrors=(
            f"{RAW_GH}/firstandthirty/nfl-tools/"
            f"{MIRROR_PINS['firstandthirty/nfl-tools']}"
            "/player_props/data/processed/fanduel_receptions_history.csv",
        ),
        per_season=False,
    ),
}


def refresh_mirror_pin(owner_repo: str, timeout: float = 60.0) -> str:
    """Current HEAD commit of a mirror repo, via ``git ls-remote``.

    Uses git's smart-HTTP transport, which works in environments where the
    github.com website / API / release assets are blocked. Returns the sha;
    updating MIRROR_PINS stays a deliberate, reviewed edit (re-verify the
    mirrored files' schemas and row counts before advancing a pin).
    """
    out = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{owner_repo}", "HEAD"],
        capture_output=True, text=True, check=True, timeout=timeout,
    )
    sha = parse_ls_remote_head(out.stdout)
    if sha is None:
        raise ValueError(f"no HEAD ref in ls-remote output for {owner_repo}")
    return sha


def parse_ls_remote_head(stdout: str) -> str | None:
    """Extract the HEAD sha from ``git ls-remote <repo> HEAD`` output."""
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "HEAD" and len(parts[0]) == 40:
            return parts[0]
    return None


def _fetch_first(urls: list[str], dest: Path) -> tuple[str, str | None]:
    """Try each URL in order; return (status, url used or None)."""
    last_err: Exception | None = None
    for url in urls:
        try:
            status = _fetch(url, dest)
        except Exception as exc:  # proxy 403s surface as HTTPError/URLError
            last_err = exc
            continue
        if status in ("downloaded", "cached"):
            return status, url
    if last_err is not None:
        return f"UNREACHABLE ({last_err})", None
    return "missing", None


def fetch_all(raw_dir: Path = RAW_DIR) -> dict[str, list]:
    """Fetch every dataset (canonical first, pinned mirrors as fallback)."""
    available: dict[str, list] = {key: [] for key in DATASETS}
    problems = 0
    for key, ds in DATASETS.items():
        seasons = list(SEASONS) if ds.per_season else [None]
        for season in seasons:
            status, url = _fetch_first(ds.urls(season), ds.dest(raw_dir, season))
            if status in ("downloaded", "cached"):
                available[key].append(season if season is not None else ds.filename)
                if status == "downloaded":
                    print(f"{key} {season or ''}: downloaded from {url}", flush=True)
            else:
                problems += 1
                print(f"{key} {season or ''}: {status}", flush=True)
    if problems:
        print(
            f"\n{problems} file(s) unavailable from both the canonical "
            "release and the pinned mirrors. The pipeline degrades "
            "gracefully (enrichment features go missing-flagged), but run "
            "this step somewhere with open internet when possible.",
            flush=True,
        )
    return available


def report(raw_dir: Path = RAW_DIR) -> None:
    print("enrichment cache availability:")
    for key, ds in DATASETS.items():
        if ds.per_season:
            have = [s for s in SEASONS if ds.dest(raw_dir, s).exists()]
            print(f"  {key:18s} seasons: {have or 'none cached'}")
        else:
            state = "cached" if ds.dest(raw_dir).exists() else "not cached"
            print(f"  {key:18s} {ds.filename}: {state}")


def _refresh_pins_report() -> None:
    for repo in MIRROR_PINS:
        try:
            head = refresh_mirror_pin(repo)
        except Exception as exc:
            print(f"  {repo}: ERROR {exc}")
            continue
        pinned = MIRROR_PINS[repo]
        drift = "" if head.startswith(pinned) or pinned == "main" else "  (pin is behind)"
        print(f"  {repo}: HEAD {head}  pinned {pinned}{drift}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--report", action="store_true",
                        help="show cache state, no fetching")
    parser.add_argument("--refresh-pins", action="store_true",
                        help="resolve each mirror's current HEAD via git ls-remote")
    args = parser.parse_args()
    if args.report:
        report(args.raw_dir)
        sys.exit(0)
    if args.refresh_pins:
        _refresh_pins_report()
        sys.exit(0)
    fetch_all(args.raw_dir)
