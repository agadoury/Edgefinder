# EdgeFinder pipeline

Python pipeline that turns raw NFL box scores + schedules into the
player-prop JSON consumed by the web app, per `docs/DATA_CONTRACT.md`.

## Run

```bash
pip install -r pipeline/requirements.txt
python3 pipeline/run_pipeline.py            # full run, writes pipeline/data/export/
python3 pipeline/run_pipeline.py --skip-download --retrain
python3 pipeline/edgefinder/validate.py     # re-check an existing export
python3 -m pytest pipeline/tests            # leakage-sensitive unit tests
```

## Data

* `hvpkod/NFL-Data` — weekly per-position box scores (fantasy.nfl.com
  actuals), seasons 2021-2025. **Quirk:** week 18 exists upstream only for
  2025; 2021-2024 cover weeks 1-17. The cancelled 2022 wk17 BUF@CIN game is
  present in hvpkod but not in the schedule; its rows are excluded.
* `nflverse/nfldata games.csv` — schedule, scores, rest, Vegas
  `spread_line` (positive = home favored, verified empirically each load)
  and `total_line`, roof/surface/temp/wind, starting QB names.
* Team codes are normalized to nfldata codes; the hvpkod mapping (`LAR` →
  `LA` since 2024) is derived from the schedule, not hardcoded.

## Design notes

* **Leak-freedom.** Every feature comes from strictly earlier weeks via
  backward as-of joins with `allow_exact_matches=False`; opponent ranks are
  recomputed as-of each week.
* **Cold starts.** Player form/usage windows roll across season boundaries
  (last-N *played* games), season-to-date columns reset each season, and
  rows with < 2 prior played career games are excluded from training and
  backtest.
* **DNP.** A row counts as played when any of touches/targets/pass yds/
  rush yds/receptions > 0 or fantasy points != 0. A genuine
  played-with-zero-usage game is indistinguishable from a DNP and is
  treated as one.
* **Models.** Per market: `HistGradientBoostingRegressor` mean model +
  quantile models at 0.05..0.95 (row-sorted for monotonicity), trained on
  2021-2024. Projection = 0.5·(mean + p50), floored at 0. Yards curves are
  a piecewise-linear CDF through the quantiles with exponential-ish tails;
  receptions sample the CDF on 0.5 steps; pass TDs use
  Poisson(λ = max(0.05, projection)) at half-lines.
* **refLine** = 50/50 blend of trailing-5-played median and season-to-date
  median, snapped to a .5 line ("what a typical fan expects").
  `overProbAtRef` is read off the exported curve itself, so the contract's
  interpolation invariant holds exactly.
* **Confidence** thresholds ((p75-p25)/max(p50,1) quartiles, ~25/50/25) are
  calibrated on the 2025 backtest predictions and stored in
  `pipeline/data/models/confidence_thresholds.json`; < 5 games played this
  season drops one level.
* **Explanations.** Group perturbation against position-conditional
  training medians on the mean model; groups with |impact| ≥
  max(1.5% of projection, ε) survive, top 3 always kept, cap 6.

## Layout

```
pipeline/
├── run_pipeline.py         # CLI orchestrator
├── edgefinder/
│   ├── download.py  load.py  features.py  train.py
│   ├── explain.py   backtest.py  export.py  validate.py
├── tests/                  # leak-sensitive unit tests
└── data/
    ├── raw/                # cached source CSVs
    ├── models/             # joblib models + thresholds + backtest preds
    └── export/             # contract JSON staging (NOT web/src/data)
```
