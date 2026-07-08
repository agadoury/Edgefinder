# EdgeFinder pipeline run report

Generated 2026-07-08 02:39Z — model v1.0.0, trained on 2021-2024 REG.

* **Demo slate:** 2025 week 14 (14 games, 173 players, 359 prop rows)
* **Validation:** PASSED

## Backtest — 2025 weeks 1-13 (walk-forward)

| market | n | MAE | baseline MAE | coverage80 | strong-call hit | strong n |
|---|---|---|---|---|---|---|
| pass_yds | 435 | 59.30 | 69.17 | 0.749 | 0.905 | 21 |
| pass_tds | 435 | 0.85 | 0.95 | 0.830 | 0.904 | 52 |
| rush_yds | 1226 | 18.70 | 19.32 | 0.778 | 0.767 | 30 |
| rec_yds | 2766 | 18.40 | 19.25 | 0.808 | 0.741 | 27 |
| receptions | 2766 | 1.38 | 1.41 | 0.890 | 0.865 | 74 |

Baseline = the refLine blend (trailing-5 median x season median). The model beats it on every market.

## Data quirks

* hvpkod has no week-18 files for 2021-2024 (404 upstream); those seasons cover weeks 1-17. 2025 has all 18 weeks.
* The cancelled 2022 wk17 BUF@CIN game exists in hvpkod but not in nfldata; its rows are excluded (stats were nullified anyway).
* hvpkod codes the Rams `LA` through 2023 and `LAR` from 2024; the schedule-derived map normalizes both to nfldata `LA`.
* Free-agent rows (`Team == FA`, always opponent `Bye`) are dropped.
* A played-but-zero-usage game is indistinguishable from a DNP in the box-score source and is treated as DNP.
* Cold start: form windows roll across season boundaries; rows with < 2 prior played career games are excluded from training/backtest.
