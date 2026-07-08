# EdgeFinder — product backlog (v2 and beyond)

v1 ships the core experience: real trained models over five markets
(passing yards, passing TDs, rushing yards, receiving yards, receptions),
a replayed 2025 week with verifiable results, player pages with
plain-English explanations, and an honest how-it-works page.

Everything below was consciously deferred, roughly in priority order.

## v2 — trust & discovery

- **Weekly "Top Edges" board, expanded.** Saved filter presets, per-market
  leaderboards, "biggest disagreements with the crowd" view, shareable
  card images for a call (social-ready PNG).
- **Full model transparency page.** Week-by-week backtest explorer (browse
  any 2025 week, see every call and outcome), interactive calibration and
  coverage charts, per-market error distributions, model changelog.
- **Matchup explorer.** Game-centric view: both teams' key players,
  defensive vulnerability by position (heat tiles), pace/weather/Vegas
  context, and the model's calls for that game in one screen.
- **Live 2026 season mode.** Weekly automated pipeline runs (cron) once
  the season starts; "last updated" freshness stamp; injury-report cutoff
  awareness (run Sun morning); slate switcher (this week vs replay demo).

## v2 — modeling

- **Injury reports as first-class features.** Official practice
  participation and game statuses (out/questionable) for the player AND
  key teammates (e.g. WR1 out boosts WR2 targets), plus opposing defense
  starters missing. Requires a licensed or scraped injury feed.
- **Play-by-play upgrade.** Move from box-score aggregates to
  play-by-play-derived features (air yards, aDOT, routes run, red-zone
  share, pressure rates, coverage schemes). Requires nflverse release
  assets (blocked in the current build environment) or a data vendor.
- **Anytime-TD and combo markets.** Anytime TD scorer, rush+rec yards,
  completions, attempts, interceptions, longest reception.
- **Distribution upgrades.** Replace per-quantile GBMs with a single
  distributional model (NGBoost / quantile ensembles with conformal
  calibration) for sharper, guaranteed-coherent intervals.
- **Teammate interaction graph.** Explicit usage-redistribution model when
  a starter is out, instead of implicit availability features.

## v3 — product

- **Accounts & watchlists.** Follow players, get a weekly digest email of
  the model's calls for your guys.
- **Alerts.** "Tell me when the model leans hard on anyone in tonight's
  game" push/email alerts.
- **Sportsbook line integration (odds API).** Compare the model's
  projection to *real* posted lines — this changes the product's promise
  from "what will happen" to "where the market disagrees", so it needs
  its own responsible-gambling review, EV framing, and legal pass.
- **Parlay sanity-checker.** Paste a parlay, get the model's joint
  probability with correlation warnings (same-game legs are correlated!).
- **Historical player pages.** Career view, season splits, home/away and
  weather splits, defense-faced quality adjustments.
- **Native mobile app / PWA install prompt.**

## Engineering debt & infra

- Automated weekly retrain + data-quality gates (row counts, distribution
  drift checks) before any export goes live.
- Model registry with versioned artifacts; A/B of model versions on
  backtest windows before promotion.
- Real database (the JSON export is fine for a static weekly slate; live
  mode wants Postgres + an API layer).
- E2E test suite (Playwright) over the three core pages.
- CDN-hosted headshots/team art once licensing allows.
