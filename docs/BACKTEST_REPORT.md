# EdgeFinder pipeline run report

Generated 2026-07-09 16:42Z — model v1.0.0, trained on 2021-2024 REG; intervals conformalized on a held-out 2024 split.

* **Demo slate:** 2025 week 14 (14 games, 173 players, 359 prop rows)
* **Validation:** PASSED

## Backtest — 2025 weeks 1-13 (walk-forward)

| market | n | MAE | baseline MAE | coverage80 | strong-call hit | strong n |
|---|---|---|---|---|---|---|
| pass_yds | 435 | 59.30 | 69.17 | 0.846 | 0.900 | 10 |
| pass_tds | 435 | 0.85 | 0.95 | 0.789 | 0.872 | 47 |
| rush_yds | 1226 | 18.70 | 19.32 | 0.834 | 0.889 | 9 |
| rec_yds | 2766 | 18.40 | 19.25 | 0.829 | 0.650 | 20 |
| receptions | 2766 | 1.38 | 1.41 | 0.817 | 0.814 | 86 |

Baseline = the refLine blend (trailing-5 median x season median). The model beats it on every market.

## Interval calibration (split conformal, 2024)

Models refit on 2021-2023 were scored on held-out 2024 (walk-forward by construction); the fixed adjustments below are applied unchanged to the 2025 backtest and the demo slate. Conformity scores never come from 2025.

* **pass_yds** — additive per-quantile deltas (n=556): p10 -10.1, p50 -7.9, p90 +19.5 (units of the stat).
* **pass_tds** — discrete Poisson layer on half-integer support (n=556): lambda = mean-model expectation x 1.0274, plus a mid-PIT conformal level map; quantiles/curves come from the continuity-corrected CDF, so low quantiles vary by player.
* **rush_yds** — additive per-quantile deltas (n=1523): p10 -0.5, p50 -0.1, p90 +5.8 (units of the stat).
* **rec_yds** — additive per-quantile deltas (n=3361): p10 +0.0, p50 -0.0, p90 +3.8 (units of the stat).
* **receptions** — discrete NB(alpha=0.1) layer on half-integer support (n=3361): lambda = mean-model expectation x 1.0092, plus a mid-PIT conformal level map; quantiles/curves come from the continuity-corrected CDF, so low quantiles vary by player.

## Data quirks

* hvpkod has no week-18 files for 2021-2024 (404 upstream); those seasons cover weeks 1-17. 2025 has all 18 weeks.
* The cancelled 2022 wk17 BUF@CIN game exists in hvpkod but not in nfldata; its rows are excluded (stats were nullified anyway).
* hvpkod codes the Rams `LA` through 2023 and `LAR` from 2024; the schedule-derived map normalizes both to nfldata `LA`.
* Free-agent rows (`Team == FA`, always opponent `Bye`) are dropped.
* A played-but-zero-usage game is indistinguishable from a DNP in the box-score source and is treated as DNP.
* Cold start: form windows roll across season boundaries; rows with < 2 prior played career games are excluded from training/backtest.
