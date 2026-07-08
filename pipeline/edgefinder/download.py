"""Download raw NFL data into the local cache.

Sources (both fetched over plain HTTPS, no auth):

- hvpkod/NFL-Data  — weekly per-position player stat lines scraped from
  fantasy.nfl.com, committed in-repo. Seasons 2021+ ship as CSV.
- nflverse/nfldata — games.csv: schedule, scores, rest days, roof/surface,
  temperature, wind, and Vegas spread/total for every game since 1999.

Files land under pipeline/data/raw/ and are never re-fetched when present,
so the pipeline can be re-run offline once the cache is warm.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

HVPKOD_BASE = (
    "https://raw.githubusercontent.com/hvpkod/NFL-Data/main/NFL-data-Players"
)
GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

SEASONS = range(2021, 2026)
WEEKS = range(1, 19)  # 18-week regular season (2021 onward)
POSITIONS = ["QB", "RB", "WR", "TE"]

PAUSE_SECONDS = 0.8  # be polite to raw.githubusercontent.com
MAX_ATTEMPTS = 6


def _fetch(url: str, dest: Path) -> str:
    """Fetch url to dest with retry/backoff. Returns a status string."""
    if dest.exists() and dest.stat().st_size > 0:
        return "cached"
    dest.parent.mkdir(parents=True, exist_ok=True)
    delay = 2.0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "edgefinder-pipeline/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
            dest.write_bytes(body)
            return "downloaded"
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return "missing"
            if err.code in (429, 500, 502, 503) and attempt < MAX_ATTEMPTS:
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < MAX_ATTEMPTS:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    return "failed"


def download_all(raw_dir: Path = RAW_DIR) -> None:
    status = _fetch(GAMES_URL, raw_dir / "games.csv")
    print(f"games.csv: {status}", flush=True)

    total = len(SEASONS) * len(WEEKS) * len(POSITIONS)
    done = 0
    missing: list[str] = []
    for season in SEASONS:
        for week in WEEKS:
            for pos in POSITIONS:
                rel = f"{season}/{week}/{pos}.csv"
                dest = raw_dir / "hvpkod" / rel
                status = _fetch(f"{HVPKOD_BASE}/{rel}", dest)
                done += 1
                if status == "missing":
                    missing.append(rel)
                if status == "downloaded":
                    time.sleep(PAUSE_SECONDS)
                if done % 40 == 0 or done == total:
                    print(f"[{done}/{total}] last={rel} ({status})", flush=True)
    if missing:
        print(f"missing files ({len(missing)}): {missing[:10]}", flush=True)
    print("download complete", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    try:
        download_all(args.raw_dir)
    except Exception as exc:  # surface a clean error for the caller
        print(f"FATAL: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
