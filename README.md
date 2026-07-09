# EdgeFinder

**Know what to expect before you bet.**

EdgeFinder is an NFL player-prop research platform for casual bettors. For
every featured player and market — passing yards, passing TDs, rushing
yards, receiving yards, receptions — a trained machine-learning model
projects the stat line, shows a full projected *range* (not just one
number), leans over or under a reference line, and explains **why** in
plain English: opponent defense, recent form, usage, game environment
(Vegas total/spread), weather, rest, and QB situation.

EdgeFinder analyzes *player output*. It does not hunt sportsbook pricing
edges, and its reference lines are typical-expectation numbers, not
posted odds.

## How it works (short version)

```
raw NFL data (2021–2025) ──► feature builder (leak-free, as-of-kickoff)
                                   │
                     gradient-boosted models per market
                     (point projection + quantile band)
                                   │
              backtest on the 2025 season, walk-forward
                                   │
        JSON export ──► Next.js app (this repo, root)
```

- **Data**: weekly player box-score lines (fantasy.nfl.com via the
  hvpkod/NFL-Data mirror) + nflverse `games.csv` (schedule, rest, roof,
  temperature, wind, Vegas spread/total, starting QBs).
- **Models**: scikit-learn `HistGradientBoostingRegressor`, one point
  model + quantile models per market, trained on 2021–2024, evaluated
  walk-forward on 2025. Passing-TD probabilities use a Poisson layer.
- **Explanations**: per-prediction factor attributions computed by
  neutralizing one factor group at a time and re-predicting — the same
  numbers the UI renders as plain-English reasons.
- **Demo slate**: the app replays a real 2025 week ("backtest replay"),
  so every call can be checked against what actually happened — flip the
  **Show results** toggle in the header.

The full pipeline → app data contract lives in
[`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md). The deferred feature
list lives in [`BACKLOG.md`](BACKLOG.md).

## Running it

### Web app (uses the committed data export — no Python needed)

```bash
npm install
npm run dev        # http://localhost:3000
```

The Next.js app lives at the repo root, so Vercel (and similar hosts)
auto-detect it with zero configuration — import the repo and deploy.

### Rebuilding the data + models

```bash
pip install -r pipeline/requirements.txt
python3 pipeline/run_pipeline.py     # download → features → train → backtest → export → validate
```

Raw data caches under `pipeline/data/raw/` (gitignored). The validated
export is written to `pipeline/data/export/` and copied into
`src/data/`, which **is** committed so the app runs out of the box.

See [`pipeline/README.md`](pipeline/README.md) for pipeline details and
module layout.

## Repo layout

```
src/, public/, package.json, next.config.ts
            Next.js app at the repo root (App Router, TypeScript,
            Tailwind; all charts hand-rolled SVG)
pipeline/   Python ML pipeline (download, features, train, backtest, explain, export, validate)
docs/       DATA_CONTRACT.md — the single source of truth between the two
BACKLOG.md  everything deliberately deferred to v2+
```

## Honesty notes

- Projections are estimates with real uncertainty; the app always shows
  the projected range and the model's backtested accuracy, including
  where it loses to a naive baseline (if it ever does).
- Reference lines are **not** sportsbook lines.
- 21+. If gambling stops being fun: 1-800-GAMBLER.
