# EdgeFinder pipeline run report

Generated 2026-07-21 11:58Z — model v1.0.0, trained on 2021-2024 REG with recency-weighted samples (half-life 3.0 seasons); intervals conformalized on a held-out 2024 split.

* **Demo slate:** 2025 week 14 (14 games, 170 players, 351 prop rows)
* **Validation:** PASSED

## Backtest — 2025 weeks 1-13 (walk-forward)

2025 is evaluation only: every model, calibration and threshold choice was made on the 2024 walk-forward split (models fit on 2021-2023), then applied here unchanged.

| market | n | MAE | baseline MAE | coverage80 | CRPS | Brier | strong-call hit | strong n |
|---|---|---|---|---|---|---|---|---|
| pass_yds | 435 | 57.45 | 69.17 | 0.807 | 33.703 | 0.2107 | 0.933 | 15 |
| pass_tds | 435 | 0.84 | 0.95 | 0.821 | 0.485 | 0.1889 | 0.868 | 53 |
| rush_yds | 1226 | 18.53 | 19.32 | 0.816 | 10.695 | 0.2312 | 1.000 | 5 |
| rec_yds | 2766 | 18.21 | 19.25 | 0.846 | 10.327 | 0.2292 | 1.000 | 12 |
| receptions | 2766 | 1.37 | 1.41 | 0.810 | 0.779 | 0.2224 | 0.865 | 111 |

Baseline = the refLine blend (trailing-5 median x season median). The model beats it on every market.

## Distributional diagnostics (M3)

Per-quantile empirical coverage P(y <= q_tau) (target = tau) and mean pinball loss; CRPS is approximated as 2x the average pinball loss across the seven quantiles.

| market | p05 | p10 | p25 | p50 | p75 | p90 | p95 | CRPS | Brier |
|---|---|---|---|---|---|---|---|---|---|
| pass_yds (coverage) | 0.083 | 0.136 | 0.278 | 0.508 | 0.724 | 0.913 | 0.949 | 33.703 | 0.2107 |
| pass_yds (pinball) | 7.288 | 12.661 | 22.446 | 28.825 | 24.615 | 13.656 | 8.471 |  |  |
| pass_tds (coverage) | 0.290 | 0.290 | 0.331 | 0.503 | 0.745 | 0.936 | 0.963 | 0.485 | 0.1889 |
| pass_tds (pinball) | 0.075 | 0.144 | 0.308 | 0.438 | 0.376 | 0.220 | 0.137 |  |  |
| rush_yds (coverage) | 0.183 | 0.205 | 0.307 | 0.532 | 0.796 | 0.898 | 0.945 | 10.695 | 0.2312 |
| rush_yds (pinball) | 1.582 | 2.902 | 6.056 | 9.091 | 8.596 | 5.597 | 3.606 |  |  |
| rec_yds (coverage) | 0.189 | 0.217 | 0.297 | 0.523 | 0.773 | 0.914 | 0.957 | 10.327 | 0.2292 |
| rec_yds (pinball) | 1.506 | 2.783 | 5.978 | 8.998 | 8.404 | 5.227 | 3.248 |  |  |
| receptions (coverage) | 0.184 | 0.205 | 0.299 | 0.530 | 0.780 | 0.914 | 0.963 | 0.779 | 0.2224 |
| receptions (pinball) | 0.127 | 0.236 | 0.486 | 0.685 | 0.603 | 0.362 | 0.227 |  |  |

Calibration-bucket drift (|predicted − actual| over the P(over) buckets) and strong-call Wilson 95% intervals:

| market | worst bucket drift | mean bucket drift (n-weighted) | strong-call hit (n) | Wilson 95% |
|---|---|---|---|---|
| pass_yds | 0.067 | 0.045 | 0.933 (15) | [0.702, 0.988] |
| pass_tds | 0.084 | 0.043 | 0.868 (53) | [0.752, 0.935] |
| rush_yds | 0.158 | 0.018 | 1.000 (5) | [0.566, 1.000] |
| rec_yds | 0.052 | 0.034 | 1.000 (12) | [0.757, 1.000] |
| receptions | 0.063 | 0.033 | 0.865 (111) | [0.789, 0.916] |

## Interval calibration (split conformal, 2024)

Models refit on 2021-2023 were scored on held-out 2024 (walk-forward by construction); the fixed adjustments below are applied unchanged to the 2025 backtest and the demo slate. Conformity scores never come from 2025.

* **pass_yds** — additive per-quantile deltas (n=556): p10 -2.5, p50 -5.4, p90 +6.1 (units of the stat).
* **pass_tds** — discrete Poisson layer on half-integer support (n=556): lambda = mean-model expectation x 1.0402, plus a mid-PIT conformal level map; quantiles/curves come from the continuity-corrected CDF, so low quantiles vary by player.
* **rush_yds** — additive per-quantile deltas (n=1523): p10 -0.1, p50 -0.0, p90 +2.9 (units of the stat).
  * P(over) shrink (M6): p' = sigmoid(-0.112 + 0.845·logit(p)) on every exported curve point, fit on the same 2024 walk-forward predictions (n=1523; 2024 cross-week Brier delta -0.00049). Quantiles are not shrunk.
* **rec_yds** — additive per-quantile deltas (n=3361): p10 +0.0, p50 -0.0, p90 +2.1 (units of the stat).
* **receptions** — discrete NB(alpha=0.1) layer on half-integer support (n=3361): lambda = mean-model expectation x 1.0000, plus a mid-PIT conformal level map; quantiles/curves come from the continuity-corrected CDF, so low quantiles vary by player.

Confidence thresholds (M12) are the relative-width quartiles of the same 2024 walk-forward calibrated quantiles (`confidence_thresholds.json`, provenance-stamped). The ~25/50/25 high/medium/low split is therefore targeted on 2024; the realized 2025 split may drift — that is the honest cost of removing the circular 2025 fit.

## Against real FanDuel closing lines (M13)

Archived FanDuel prop snapshots (pass yds + receptions) matched to the 2025 walk-forward backtest by normalized player name and schedule-derived week; the FanDuel number is the last archived snapshot before kickoff. Everything else in this report grades the model against its own refLine — this section is the honest check against a real market. Evaluation only: none of it feeds the models, and it is deliberately NOT exported to meta.json (contract frozen; a candidate for a future how-it-works section).

| market | n matched | model MAE | FD line MAE | Brier at FD | lean hit rate (n) | Wilson 95% | strong hit rate (n) | Wilson 95% |
|---|---|---|---|---|---|---|---|---|
| pass_yds | 375 | 56.53 | 53.52 | 0.2594 | 0.513 (267) | [0.453, 0.572] | 1.000 (2) | [0.342, 1.000] |
| receptions | 1771 | 1.63 | 1.59 | 0.2592 | 0.546 (1391) | [0.519, 0.572] | 0.538 (13) | [0.291, 0.768] |

P(over FanDuel line) calibration:

* **pass_yds** — [0.15] pred 0.21 act 0.53 n=38 | [0.35] pred 0.36 act 0.43 n=44 | [0.45] pred 0.45 act 0.50 n=125 | [0.55] pred 0.54 act 0.47 n=120 | [0.65] pred 0.64 act 0.70 n=40 | [0.85] pred 0.76 act 0.50 n=8
* **receptions** — [0.15] pred 0.23 act 0.43 n=202 | [0.35] pred 0.35 act 0.41 n=427 | [0.45] pred 0.45 act 0.50 n=485 | [0.55] pred 0.55 act 0.46 n=393 | [0.65] pred 0.64 act 0.54 n=197 | [0.85] pred 0.76 act 0.42 n=67

A ~52.4% hit rate is the break-even at standard -110 pricing (the archived FanDuel prices on our leaned sides imply 52.9% (pass_yds) and 55.6% (receptions)). The hit rates above carry wide intervals and sit near that bar — **we are NOT claiming market edge**; against real closing lines the model is a study tool, not a money machine. Snapshots are near-closing (median hours to kickoff reported per market: pass_yds 1.6h, receptions 1.6h), not the literal final tick. 2023-2024 archive seasons are excluded because the shipped models train through 2024 — scoring them here would not be walk-forward.

## Data quirks

* hvpkod has no week-18 files for 2021-2024 (404 upstream); 2021-2023 cover weeks 1-17 and 2024 stops at week 16. 2025 has all 18 weeks.
* The cancelled 2022 wk17 BUF@CIN game exists in hvpkod but not in nfldata; its rows are excluded (stats were nullified anyway).
* hvpkod codes the Rams `LA` through 2023 and `LAR` from 2024; the schedule-derived map normalizes both to nfldata `LA`.
* hvpkod's 2021-2024 archives retro-apply a player's end-of-season team to every week; the enrichment joins (enrich_join.py) recover traded players via an unambiguous name-only fallback.
* Free-agent rows (`Team == FA`, always opponent `Bye`) are dropped.
* A played-but-zero-usage game is indistinguishable from a DNP in the box-score source and is treated as DNP.
* Cold start: form windows roll across season boundaries; rows with < 2 prior played career games are excluded from training/backtest.
* Enrichment sources (snap counts / injuries / player stats) are join-coverage-gated at 90% per enrich_join.py; players ruled Out on the week's report are excluded from the demo slate.
