"""Fetch free nflverse enrichment datasets (canonical open-internet sources).

Downloads, per season 2021-2025, from nflverse-data GitHub releases:

- snap_counts_{season}.csv   — offensive snap counts / snap share
- injuries_{season}.csv      — official practice participation + game status
- ngs_{season}_receiving.csv.gz / ngs_{season}_passing.csv.gz
                             — Next Gen Stats (air yards, aDOT, separation)

All of it is free, public data. The catch: GitHub release assets redirect
through github.com, which SOME sandboxed environments block (this repo's
original build sandbox did). This module therefore degrades gracefully:
every file that can't be fetched is reported and skipped, and the caller
decides what to do with partial availability. On an open-internet machine
(your laptop, GitHub Actions runners) everything downloads normally.

These datasets are not yet consumed by features.py — wiring them in is
tracked in BACKLOG.md (roadmap items M9/M10) and should happen only after
their schemas have been validated against real downloads.

Usage:
    python3 pipeline/edgefinder/enrich.py           # fetch into the raw cache
    python3 pipeline/edgefinder/enrich.py --report  # availability report only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from download import RAW_DIR, SEASONS, _fetch

RELEASE_BASE = "https://github.com/nflverse/nflverse-data/releases/download"

DATASETS: dict[str, str] = {
    # dataset name -> URL template ({season} substituted)
    "snap_counts": f"{RELEASE_BASE}/snap_counts/snap_counts_{{season}}.csv",
    "injuries": f"{RELEASE_BASE}/injuries/injuries_{{season}}.csv",
    "ngs_receiving": f"{RELEASE_BASE}/nextgen_stats/ngs_{{season}}_receiving.csv.gz",
    "ngs_passing": f"{RELEASE_BASE}/nextgen_stats/ngs_{{season}}_passing.csv.gz",
}


def fetch_all(raw_dir: Path = RAW_DIR) -> dict[str, list[int]]:
    """Fetch every dataset/season pair. Returns {dataset: [seasons fetched or cached]}."""
    available: dict[str, list[int]] = {name: [] for name in DATASETS}
    blocked = 0
    for name, template in DATASETS.items():
        for season in SEASONS:
            url = template.format(season=season)
            dest = raw_dir / "enrichment" / name / Path(url).name
            try:
                status = _fetch(url, dest)
            except Exception as exc:  # proxy 403s surface as HTTPError/URLError
                print(f"{name} {season}: UNREACHABLE ({exc})", flush=True)
                blocked += 1
                continue
            if status in ("downloaded", "cached"):
                available[name].append(season)
            else:
                print(f"{name} {season}: {status}", flush=True)
    if blocked:
        print(
            f"\n{blocked} file(s) unreachable. If this machine sits behind a "
            "network policy that blocks github.com release assets, run this "
            "step somewhere with open internet (e.g. the weekly GitHub "
            "Action) — the cache is reused afterwards.",
            flush=True,
        )
    return available


def report(raw_dir: Path = RAW_DIR) -> None:
    print("enrichment cache availability:")
    for name in DATASETS:
        have = sorted(
            int(p.stem.split("_")[-1].split(".")[0])
            for p in (raw_dir / "enrichment" / name).glob("*")
        ) if (raw_dir / "enrichment" / name).exists() else []
        print(f"  {name:15s} seasons: {have or 'none cached'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--report", action="store_true", help="show cache state, no fetching")
    args = parser.parse_args()
    if args.report:
        report(args.raw_dir)
        sys.exit(0)
    fetch_all(args.raw_dir)
