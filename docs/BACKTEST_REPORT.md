# EdgeFinder pipeline run report

Generated 2026-07-09 19:09Z — model v1.0.0, trained on 2021-2024 REG with recency-weighted samples (half-life 3.0 seasons); intervals conformalized on a held-out 2024 split.

* **Demo slate:** 2025 week 14 (14 games, 173 players, 359 prop rows)
* **Validation:** PASSED

## Backtest — 2025 weeks 1-13 (walk-forward)

2025 is evaluation only: every model, calibration and threshold choice was made on the 2024 walk-forward split (models fit on 2021-2023), then applied here unchanged.

| market | n | MAE | baseline MAE | coverage80 | CRPS | Brier | strong-call hit | strong n |
|---|---|---|---|---|---|---|---|---|
| pass_yds | 435 | 56.77 | 69.17 | 0.821 | 33.142 | 0.2075 | 1.000 | 10 |
| pass_tds | 435 | 0.86 | 0.95 | 0.809 | 0.482 | 0.1862 | 0.939 | 49 |
| rush_yds | 1226 | 18.59 | 19.32 | 0.830 | 10.820 | 0.2347 | 1.000 | 1 |
| rec_yds | 2766 | 18.36 | 19.25 | 0.903 | 10.508 | 0.2343 | 0.889 | 9 |
| receptions | 2766 | 1.39 | 1.41 | 0.809 | 0.787 | 0.2269 | 0.872 | 94 |

Baseline = the refLine blend (trailing-5 median x season median). The model beats it on every market.

## Distributional diagnostics (M3)

Per-quantile empirical coverage P(y <= q_tau) (target = tau) and mean pinball loss; CRPS is approximated as 2x the average pinball loss across the seven quantiles.

| market | p05 | p10 | p25 | p50 | p75 | p90 | p95 | CRPS | Brier |
|---|---|---|---|---|---|---|---|---|---|
| pass_yds (coverage) | 0.087 | 0.131 | 0.264 | 0.517 | 0.754 | 0.917 | 0.954 | 33.142 | 0.2075 |
| pass_yds (pinball) | 7.286 | 12.117 | 22.371 | 28.196 | 23.297 | 13.799 | 8.932 |  |  |
| pass_tds (coverage) | 0.290 | 0.290 | 0.329 | 0.508 | 0.752 | 0.922 | 0.972 | 0.482 | 0.1862 |
| pass_tds (pinball) | 0.072 | 0.143 | 0.307 | 0.438 | 0.376 | 0.219 | 0.131 |  |  |
| rush_yds (coverage) | 0.183 | 0.191 | 0.307 | 0.519 | 0.794 | 0.900 | 0.945 | 10.820 | 0.2347 |
| rush_yds (pinball) | 1.590 | 2.978 | 6.093 | 9.175 | 8.765 | 5.611 | 3.659 |  |  |
| rec_yds (coverage) | 0.189 | 0.189 | 0.300 | 0.519 | 0.773 | 0.914 | 0.957 | 10.508 | 0.2343 |
| rec_yds (pinball) | 1.506 | 2.980 | 6.021 | 9.105 | 8.562 | 5.302 | 3.304 |  |  |
| receptions (coverage) | 0.184 | 0.206 | 0.300 | 0.526 | 0.761 | 0.909 | 0.962 | 0.787 | 0.2269 |
| receptions (pinball) | 0.128 | 0.236 | 0.489 | 0.693 | 0.610 | 0.370 | 0.231 |  |  |

Calibration-bucket drift (|predicted − actual| over the P(over) buckets) and strong-call Wilson 95% intervals:

| market | worst bucket drift | mean bucket drift (n-weighted) | strong-call hit (n) | Wilson 95% |
|---|---|---|---|---|
| pass_yds | 0.075 | 0.022 | 1.000 (10) | [0.722, 1.000] |
| pass_tds | 0.130 | 0.037 | 0.939 (49) | [0.835, 0.979] |
| rush_yds | 0.186 | 0.022 | 1.000 (1) | [0.207, 1.000] |
| rec_yds | 0.064 | 0.034 | 0.889 (9) | [0.565, 0.980] |
| receptions | 0.079 | 0.032 | 0.872 (94) | [0.790, 0.925] |

## Interval calibration (split conformal, 2024)

Models refit on 2021-2023 were scored on held-out 2024 (walk-forward by construction); the fixed adjustments below are applied unchanged to the 2025 backtest and the demo slate. Conformity scores never come from 2025.

* **pass_yds** — additive per-quantile deltas (n=556): p10 -4.0, p50 -4.8, p90 +8.6 (units of the stat).
* **pass_tds** — discrete Poisson layer on half-integer support (n=556): lambda = mean-model expectation x 1.0398, plus a mid-PIT conformal level map; quantiles/curves come from the continuity-corrected CDF, so low quantiles vary by player.
* **rush_yds** — additive per-quantile deltas (n=1523): p10 +0.0, p50 -0.0, p90 +2.5 (units of the stat).
  * P(over) shrink (M6): p' = sigmoid(-0.125 + 0.776·logit(p)) on every exported curve point, fit on the same 2024 walk-forward predictions (n=1523; 2024 cross-week Brier delta -0.00115). Quantiles are not shrunk.
* **rec_yds** — additive per-quantile deltas (n=3361): p10 +0.0, p50 -0.0, p90 +2.9 (units of the stat).
* **receptions** — discrete NB(alpha=0.1) layer on half-integer support (n=3361): lambda = mean-model expectation x 1.0053, plus a mid-PIT conformal level map; quantiles/curves come from the continuity-corrected CDF, so low quantiles vary by player.

Confidence thresholds (M12) are the relative-width quartiles of the same 2024 walk-forward calibrated quantiles (`confidence_thresholds.json`, provenance-stamped). The ~25/50/25 high/medium/low split is therefore targeted on 2024; the realized 2025 split may drift — that is the honest cost of removing the circular 2025 fit.

## Data quirks

* hvpkod has no week-18 files for 2021-2024 (404 upstream); those seasons cover weeks 1-17. 2025 has all 18 weeks.
* The cancelled 2022 wk17 BUF@CIN game exists in hvpkod but not in nfldata; its rows are excluded (stats were nullified anyway).
* hvpkod codes the Rams `LA` through 2023 and `LAR` from 2024; the schedule-derived map normalizes both to nfldata `LA`.
* Free-agent rows (`Team == FA`, always opponent `Bye`) are dropped.
* A played-but-zero-usage game is indistinguishable from a DNP in the box-score source and is treated as DNP.
* Cold start: form windows roll across season boundaries; rows with < 2 prior played career games are excluded from training/backtest.
