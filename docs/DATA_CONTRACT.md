# EdgeFinder data contract — pipeline → web

The Python pipeline (`pipeline/`) is the only writer of `web/src/data/`.
The Next.js app (`web/`) is the only reader. Neither side may deviate from
this document; change the contract first, then both sides.

All JSON is UTF-8, camelCase keys. Probabilities are floats in [0, 1].
Projections/yardage numbers are rounded to 1 decimal. Team codes are
canonical **nfldata** codes (`LA` for the Rams, `WAS`, `JAX`, `LV`, …);
the pipeline normalizes any source codes into these.

## Files

```
web/src/data/
├── meta.json              # season/week, markets, model card numbers
├── slate.json             # demo-week games + player-prop index rows
├── players/{playerId}.json  # one file per slate player: full detail
└── headshots.json         # OPTIONAL: playerId -> portrait URL
```

`headshots.json` is produced by `pipeline/edgefinder/headshots.py` (name
matching against the DynastyProcess ID crosswalk, ESPN headshot CDN
URLs). It is optional: if the file is absent, a player has no entry, or
an image fails to load in the browser, the app falls back to the
team-colored monogram avatar.

## Markets

| id           | label            | unit       | positions        | line step |
|--------------|------------------|------------|------------------|-----------|
| `pass_yds`   | Passing Yards    | yards      | QB               | 2.5       |
| `pass_tds`   | Passing TDs      | touchdowns | QB               | 0.5       |
| `rush_yds`   | Rushing Yards    | yards      | RB, QB           | 2.5       |
| `rec_yds`    | Receiving Yards  | yards      | WR, TE, RB       | 2.5       |
| `receptions` | Receptions       | catches    | WR, TE, RB       | 0.5       |

## Factor groups

Every explanation factor belongs to one group. The frontend maps group →
icon; the pipeline supplies the human-readable `label`/`detail` text with
live numbers baked in.

`recent_form`, `usage_role`, `opp_defense`, `game_environment`,
`weather`, `rest_schedule`, `qb_situation`, `home_away`

## meta.json

```jsonc
{
  "generatedAt": "2026-07-08T12:00:00Z",
  "season": 2025,
  "week": 14,                      // the replayed demo week
  "mode": "backtest_replay",
  "modelVersion": "1.0.0",
  "trainSeasons": [2021, 2022, 2023, 2024],
  "markets": [
    { "id": "pass_yds", "label": "Passing Yards", "unit": "yards",
      "positions": ["QB"], "lineStep": 2.5 }
  ],
  "backtest": {                     // evaluated on 2025 weeks 1..(week-1)
    "season": 2025,
    "weeksEvaluated": 13,
    "byMarket": {
      "pass_yds": {
        "n": 380,                   // player-games evaluated
        "mae": 58.3,                // mean absolute error, stat units
        "baselineMae": 66.1,        // naive trailing-median baseline MAE
        "coverage80": 0.81,         // share of actuals inside [p10, p90]
        "strongCallHitRate": 0.62,  // hit rate of leans with strength >= 60
        "strongCallN": 85,
        "calibration": [            // P(over ref line) buckets
          { "bucketMid": 0.35, "predicted": 0.36, "actual": 0.34, "n": 60 }
        ]
      }
    }
  }
}
```

## slate.json

```jsonc
{
  "season": 2025,
  "week": 14,
  "games": [
    {
      "gameId": "2025_14_BUF_TB",
      "away": "BUF", "home": "TB",
      "kickoff": "2025-12-07T13:00:00-05:00",  // gameday+gametime, US/Eastern
      "roof": "outdoors",            // outdoors | dome | closed | open
      "surface": "grass",
      "tempF": 41,                   // null when dome/unknown
      "windMph": 12,                 // null when dome/unknown
      "vegasTotal": 47.5,
      "homeSpread": -3.5,            // negative = home favored
      "stadium": "Raymond James Stadium",
      "awayQb": "Josh Allen", "homeQb": "Baker Mayfield"
    }
  ],
  "props": [                         // one row per player+market (index rows)
    {
      "playerId": "2560955",
      "name": "Josh Allen",
      "team": "BUF", "pos": "QB", "opponent": "TB", "home": false,
      "gameId": "2025_14_BUF_TB",
      "market": "pass_yds",
      "projection": 261.4,
      "refLine": 249.5,
      "overProbAtRef": 0.58,
      "lean": "over",               // over | under | neutral (|p-0.5| < 0.04)
      "strength": 16,               // 0-100 edge score, see below
      "confidence": "high",         // high | medium | low
      "actual": 287.0,              // null if DNP
      "result": "over"              // over | under | push | dnp
    }
  ]
}
```

`strength` = round(100 × min(1, 2·|overProbAtRef − 0.5| × confMult)) where
confMult is 1.0/0.85/0.7 for high/medium/low. It answers "how hard does
the model lean?" — NOT "is this +EV vs a sportsbook".

## players/{playerId}.json

```jsonc
{
  "playerId": "2560955",
  "name": "Josh Allen",
  "team": "BUF", "pos": "QB", "opponent": "TB", "home": false,
  "gameId": "2025_14_BUF_TB",
  "gamesPlayed2025": 12,            // before demo week
  "props": [
    {
      "market": "pass_yds",
      "projection": 261.4,
      "quantiles": { "p10": 178.0, "p25": 214.0, "p50": 259.0,
                     "p75": 301.0, "p90": 344.0 },
      "probCurve": [                 // dense P(actual > line) curve, sorted
        { "line": 150.0, "over": 0.93 },   // by line ascending, ~40 points
        { "line": 155.0, "over": 0.92 }    // spanning ~p02..p98; strictly
      ],                                    // non-increasing `over`
      "refLine": 249.5,
      "overProbAtRef": 0.58,
      "lean": "over",
      "strength": 16,
      "confidence": "high",
      "confidenceReason": "12 games of steady volume this season",
      "verdict": "The model projects 261 passing yards — it gives Josh a 58% chance to clear a 249.5-yard line.",
      "factors": [                   // sorted by |impact| desc, max 6
        {
          "group": "opp_defense",
          "direction": "up",         // up | down
          "impact": 12.3,            // stat units added/removed vs baseline
          "label": "Tampa Bay allows 251 passing yards per game — 6th most in the NFL",
          "detail": "Defenses this generous have boosted QB output all season; the model raises Josh's projection accordingly."
        }
      ],
      "actual": 287.0,
      "result": "over"
    }
  ],
  "recentGames": [                   // last 10 played, newest first
    { "season": 2025, "week": 13, "opponent": "NE", "home": true,
      "stats": { "pass_yds": 154.0, "pass_tds": 1, "rush_yds": 30.0,
                 "rec_yds": 0.0, "receptions": 0 } }
  ],
  "seasonAvgs": { "pass_yds": 240.1, "pass_tds": 1.8, "rush_yds": 41.2 },
  "modelHistory": [                  // model's earlier 2025 calls, newest first
    { "week": 13, "market": "pass_yds", "projection": 233.0,
      "refLine": 240.5, "lean": "under", "actual": 154.0, "result": "under" }
  ]
}
```

## Frontend interpolation rule

P(over) for a user-chosen line is linear interpolation on `probCurve`
between the two bracketing points; clamp to the curve's end values outside
its range. The slider snaps to the market's `lineStep`.

## Invariants the pipeline guarantees (and validates before export)

1. Every `props[].playerId` in slate.json has a `players/{id}.json`.
2. Every `gameId` referenced by a prop exists in `games`.
3. Quantiles are non-decreasing p10 ≤ p25 ≤ p50 ≤ p75 ≤ p90.
4. `probCurve.over` is non-increasing as `line` increases.
5. `overProbAtRef` equals interpolating `probCurve` at `refLine` (±0.01).
6. Every prop has 1-6 factors; every factor group is from the fixed list.
7. All numbers finite (no NaN/Infinity serialized).
8. `result` is consistent with `actual` vs `refLine` (over/under/push) or
   `dnp` when `actual` is null.
9. No feature used by the model may draw on data from the predicted game
   or later weeks (enforced by construction; spot-checked in tests).
```
