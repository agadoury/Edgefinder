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
  actuals), seasons 2021-2025. **Quirks:** week 18 exists upstream only
  for 2025; 2021-2023 cover weeks 1-17 and 2024 stops at week 16. The
  cancelled 2022 wk17 BUF@CIN game is present in hvpkod but not in the
  schedule; its rows are excluded. The 2021-2024 archives retro-apply a
  player's end-of-season team to every week (traded players show their
  final team all season) — the enrichment join compensates (below).
* `nflverse/nfldata games.csv` — schedule, scores, rest, Vegas
  `spread_line` (positive = home favored, verified empirically each load)
  and `total_line`, roof/surface/temp/wind, starting QB names.
* Team codes are normalized to nfldata codes; the hvpkod mapping (`LAR` →
  `LA` since 2024) is derived from the schedule, not hardcoded.

### Enrichment (M9/M10/M13), cached under `data/raw/enrichment/`

Fetched by `edgefinder/enrich.py` — canonical nflverse release URLs first,
then mirrors PINNED to specific commits (personal repos; pins protect
against silent drift, `--refresh-pins` re-resolves HEADs via
`git ls-remote` smart-HTTP, which works even where github.com pages are
blocked):

* `snap_counts_{2021..2025}.csv.gz` — offensive snap share per player-game.
* `injuries_{2021..2025}.csv.gz` — official game-status + practice
  designations (2025 adds a `season_type` column; handled).
* `stats_player_week_{2021..2025}.csv` — target share, air-yards share,
  WOPR, RACR, air yards.
* `props/fanduel_*_history.csv` — archived FanDuel prop line snapshots
  (pass yds + receptions, Sep 2023-Jan 2026). Evaluation only (M13).

`edgefinder/enrich_join.py` keys these onto our player-weeks by
normalized name + team + season/week with a two-stage join (exact team
first, then a name-only rescue restricted to keys unambiguous on both
sides — this recovers traded players hit by the hvpkod retro-team quirk).
Team codes are verified against the schedule every load (all three
sources currently ship nfldata-canonical codes). Join coverage is printed
per source per season and gated at >90% before a source may feed
features; measured on the current cache: snap counts 98.9-99.4% of played
player-weeks, player stats 98.2-100%, injuries 99.3-100% of
fantasy-relevant report rows. Unjoinable rows keep NaN plus an explicit
missing indicator — never silent zeros.

## Design notes

* **Leak-freedom.** Every feature comes from strictly earlier weeks via
  backward as-of joins with `allow_exact_matches=False`; opponent ranks are
  recomputed as-of each week. One documented exception: injury-report
  features (M10) join EXACTLY on the predicted week, because game-status
  and practice designations are published before kickoff — never a future
  week (leak tests assert both directions).
* **Enrichment features (M9/M10).** Candidate bundles were validated
  bundle-wise on the 2024 split (`validation.py --exp enrich`,
  pre-registered rule in `exp_enrich`): **snap share KEPT** (rolling
  offense_pct 3/5/8 + last game + trend/delta → `usage_role`; 2024 mean
  dMAE -1.20%, dCRPS -0.75%), **injuries KEPT** (own
  Questionable/Doubtful + practice status + same-position and top-3-target
  teammates-Out counts → `rest_schedule`; mean dMAE -0.09%, dCRPS
  -0.21%), **air yards DROPPED** (mean dMAE +0.09%, dCRPS +0.17% — it
  helps rec_yds (-0.50% MAE, -0.71% CRPS) but degrades pass/rush; kept
  buildable, like the M4 position flags, for a future per-market
  feature-list experiment). Players ruled **Out** on the week's report
  never make the demo slate.
* **FanDuel benchmark (M13, evaluation only).** `fanduel_benchmark.py`
  matches archived FanDuel near-closing snapshots (pass yds +
  receptions) to the 2025 backtest by normalized name +
  schedule-derived week and reports model-vs-line MAE, P(over FD line)
  calibration, and lean hit rates with Wilson intervals in REPORT.md /
  docs/BACKTEST_REPORT.md. Deliberately NOT exported to meta.json (the
  app contract stays frozen). Honest headline: the model does not beat
  the closing line as a point predictor, and lean hit rates sit near the
  -110 break-even — no market-edge claims anywhere.
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
  2021-2024 with recency-weighted samples
  (`0.5 ** (seasons_ago / half_life)`, half-life 3 seasons — picked from a
  small grid on the 2024 walk-forward split; early seasons are
  down-weighted, never dropped). Depths are probed per loss with 2024 held
  out: mean depth by MAE, quantile depth by pinball at q10/q90.
  Projection = 0.5·(mean + p50), floored at 0. Yards curves are
  a piecewise-linear CDF through the (calibrated) quantiles with
  exponential-ish tails; count markets (receptions, pass TDs) use a
  calibrated discrete Poisson/negative-binomial layer with
  λ = mean-model expectation × a 2024-fit scale (NOT the mean/median
  blend, whose count median ran ~0.15 TD low).
* **Interval calibration (split conformal, 2024-only).** A second copy of
  each market's models is fit on 2021-2023 and scored on held-out 2024
  (features are as-of, so those predictions are walk-forward); the fixed
  adjustments are then applied unchanged to the 2025 backtest and the demo
  slate — conformity scores never come from 2025. Yardage markets get
  per-quantile additive deltas (finite-sample-corrected residual
  quantiles, re-sorted and floored at 0); count markets get the discrete
  layer above plus a mid-PIT conformal level map, with quantiles/curves
  read off the continuity-corrected CDF on half-integer support — so low
  quantiles vary by player instead of collapsing to 0, and integer lines
  exclude the push mass. Params: `pipeline/data/models/conformal.json`.
* **P(over) shrinkage (M6, 2024-fit).** Yardage-market curves ran
  overconfident in the 0.7+ region; a per-market 2-parameter Platt map
  `p' = σ(a + b·logit(p))` is fit on the 2024 walk-forward P(over ref)
  predictions and applied to every exported curve point (monotone by
  construction, so curves stay non-increasing). A market keeps its map
  only when it transfers across 2024 week halves (even/odd
  cross-validation on Brier). Quantiles are NOT shrunk — they carry the
  conformal coverage guarantee. Params live in `conformal.json`.
* **refLine** = 50/50 blend of trailing-5-played median and season-to-date
  median, snapped to a .5 line ("what a typical fan expects").
  `overProbAtRef` is read off the exported curve itself, so the contract's
  interpolation invariant holds exactly.
* **Confidence** thresholds ((p75-p25)/max(p50,1) quartiles, ~25/50/25) are
  fit on the 2024 walk-forward calibrated quantiles (M12 — previously the
  2025 backtest predictions, which was circular because confidence feeds
  strength and strength gates the strong-call metric) and stored with
  provenance in `pipeline/data/models/confidence_thresholds.json`;
  < 5 games played this season drops one level.
* **Evaluation discipline.** 2025 weeks 1-13 are the final exam: every
  selection (features, depths, recency half-life, calibration constants,
  thresholds) is made on the 2024 walk-forward split via
  `edgefinder/validation.py`, then applied to 2025 unchanged. The backtest
  reports per-quantile coverage/pinball, a CRPS approximation, Brier and
  Wilson intervals (M3) alongside MAE/coverage80.
* **Explanations.** Group perturbation against position-conditional
  training medians on the mean model; groups with |impact| ≥
  max(1.5% of projection, ε) survive, top 3 always kept, cap 6.
* **Headline polarity (U11).** Every factor headline is emitted from
  `explain.HEADLINE_TEMPLATES`, where each template declares the
  direction its stat framing implies (up/down/neutral/contrast). When a
  group's net impact contradicts its stat framing (e.g. fewest-yards-
  allowed defense but a positive impact), the renderer switches to a
  contrast headline that leads with the net story ("Season stats say
  stingy — … — but recent games say beatable; nets out about +14 yds"),
  falling back to a neutral no-direction headline when the group's own
  features can't support a counter-story. The registry doubles as a
  label→polarity classifier; `tests/test_factor_copy.py` walks every
  exported factor and asserts headline polarity ∈ {arrow direction,
  contrast, neutral}.

## Layout

```
pipeline/
├── run_pipeline.py         # CLI orchestrator
├── edgefinder/
│   ├── download.py  enrich.py  load.py  enrich_join.py
│   ├── features.py  train.py  conformal.py  metrics.py  validation.py
│   ├── explain.py   backtest.py  fanduel_benchmark.py
│   ├── export.py    validate.py  headshots.py
├── tests/                  # leak-sensitive unit tests
└── data/
    ├── raw/                # cached source CSVs (+ raw/enrichment/)
    ├── models/             # joblib models + thresholds + backtest preds
    └── export/             # contract JSON staging (NOT src/data)
```
