# EdgeFinder — Prioritized Improvement Roadmap

> **Status (2026-07-09):** the Top 10 below is fully shipped — conformal interval calibration, pass-TD lambda fix, discrete receptions layer, portal tooltips, P(over) column + lean-consistent deltas, strength tiers, My Players watchlist, your-book's-line input, model fair line + alt-line ladder, Pick 'Em Before You Peek, game hub pages, the filtered-record fix, and live coverage copy.

*Synthesis of four expert lens reviews: **engagement-loops**, **ux-friction**, **ml-accuracy**, **predictive-value**. Every item below traces to a lens report; merged duplicates note all sources. Compiled 2026-07-09.*

---

## 1. Executive summary

EdgeFinder's moat is its honesty — the "we take the L" voice, the replay format that shows misses at equal weight to hits, the calibration explainer, the exemplary responsible-gambling posture — and all four reviews independently confirmed that posture is real (no dark patterns found; no target leakage found in the feature pipeline). But the same reviews found that the trust surfaces are quietly undermined in three ways. First, presentation bugs make the honest product look broken or dishonest: every board column tooltip renders 100% clipped, 12 rows show a green "+0.3" delta beside an UNDER pill with no reconciliation, the revealed record ignores active filters ("158 hits" shown even when filtered to one team), and the range copy promises "8 times out of 10" while the shipped backtest says 74.9% for pass yards. Second, the model itself overstates its certainty: low quantiles are degenerate constants for count markets (receptions p05/p10 = 0 for 100% of rows), pass-TD probabilities are biased low in all six calibration buckets by a one-line lambda bug, and 80% intervals actually cover 75–78% on yardage markets — all verified empirically on the 7,628-row walk-forward CSV, all fixable with small, provable wrappers (simulated CQR gain: 0.752 → 0.840). Third, the product has no loop and no memory: the reveal toggle is a one-shot spoiler spent forever in localStorage, game cards are dead ends, there is no watchlist, no search, no fair-line or book-line tooling — so the best data product in the category behaves like a brochure.

The roadmap sequences work by compounding effect: **trust → retention → accuracy**. Phase one (nearly all Small-effort) makes what is already shipped legible and true — un-clip the tooltips, reconcile the delta/lean contradiction by surfacing P(over), fix the pass-TD lambda, conformalize the intervals, label ranges with their real coverage. Phase two converts the replay's one-shot reveal into a self-renewing weekly game — pick-em before you peek, a watchlist, team personalization, game hub pages, and the Tuesday recap ritual — every mechanic money-free, streak-free, and grading hits and misses with equal weight. Phase three ships the decision tools the data already supports (type your book's line, model fair line, break-even check, correlation warnings), which deliberately move users toward *fewer, better-understood* decisions — most break-even checks will honestly conclude "no edge," and that is styled as a first-class outcome. A final tranche (weekly retraining cadence, injury feeds, real-sportsbook-line benchmarking, the two-beat digest) is staged for 2026 live-season readiness. Every idea that brushed the responsible-gambling line — streak amplification, urgency, loss-framed re-engagement, bet-slip adjacency — was cut and is documented below so it stays cut.

---

## 2. Top 10 next moves

Chosen across all lenses by impact-per-effort, biased toward items that compound (trust → retention → accuracy).

| Rank | Item | Why it wins | Impact | Effort | Category | Source lens |
|---|---|---|---|---|---|---|
| 1 | **Conformalized quantile regression (CQR) wrapper on exported bands** | Provable coverage fix with no retraining — simulated on the real backtest CSV: pass yds 0.752 → 0.840. Every downstream trust surface (ranges, P(over), strength, strong calls) inherits the correction. | 5 | S | calibration | ml-accuracy |
| 2 | **Un-clip the board's column-header tooltips** | All six header tooltips render 100% clipped — the board's core vocabulary (Strength, Lean, Confidence) is literally never explained on desktop. A portal fix unlocks comprehension for every visitor. | 5 | S | comprehension-bugfix | ux-friction |
| 3 | **Type YOUR book's line (numeric input)** | Users decide against their book's line, which the snapped slider literally cannot reach (e.g. 250.5 vs a 249.5 ref). ~30 lines in MarketCard turns the toy into a tool. | 5 | S | line-tools | predictive-value |
| 4 | **Model fair line + alt-line ladder** | The dense probCurve is already shipped but consumed one line at a time; the fair line (50/50 crossing) is the most compressed statement of the model's opinion and is currently never shown. Pure frontend. | 5 | S | line-tools | predictive-value |
| 5 | **Pick 'Em Before You Peek (beat-the-model mode)** | Converts the one-shot reveal — the product's best moment, currently spent forever after one flip — into a self-renewing weekly game of prediction practice. Seeds the season ledger, the Tuesday recap, and the 2026 cadence. Fully client-side v1; money-free by design. | 5 | M | core-loop | engagement-loops (also ux-friction #7, predictive-value #13) |
| 6 | **Resolve the "green +0.3 but lean UNDER" contradiction + surface P(over)** | 12 rows produce the casual's first "this thing is broken" moment; the fix (color delta by lean, show `overProbAtRef`) simultaneously puts the decision-grade number on the board that every downstream tool speaks in. | 5 | M | comprehension | ux-friction (also predictive-value #6) |
| 7 | **Fix the pass-TDs Poisson lambda** | One line (`lam = projection` uses a mean/median blend ~0.15 TD low) biases P(over) low in **all six** calibration buckets; the fix closes two-thirds of the aggregate bias. Best accuracy-per-keystroke in the whole review. | 4 | S | bug-fix | ml-accuracy |
| 8 | **Plain-English strength tiers, everywhere the naked number appears** | A bare "56" on a mobile card is a meaningless integer; tiers ("Strong · 81") are already justified by the backtest and honestly citable. Includes restoring the Confidence badge on mobile cards. | 4 | S | comprehension | ux-friction |
| 9 | **My Players watchlist** | The cheapest possible "reason to come back": the only persistence today is the reveal flag. Stars + a "My players" pill personalize a 359-row board, and the watchlist seeds the 2026 digest. | 4 | S | personalization | engagement-loops |
| 10 | **Game hub pages (un-dead-end the game cards)** | The only defect flagged independently by **three** lenses: cards have hover affordance but no link, while "I'm watching this game — what are the calls?" is the highest-intent moment of the week. v1 is a board filter; static `/games/[gameId]` pages unlock the correlation lens later. | 4 | M | navigation | ux-friction (also engagement-loops #10, predictive-value #9) |

**Sequencing note:** ranks 1–4 and 7–9 are all Small-effort and independent — they can land in the first sprint. Rank 5 (pick-em) is the retention keystone and should start immediately after, since ranks 5 → Tuesday recap → season ledger → 2026 digest form a dependency chain.

---

## 3. Themed backlogs

Items retain their source lens's WHY / HOW / IMPACT / EFFORT / CATEGORY format. Merged duplicates appear once, with all raising lenses noted. 50 deduplicated items from 53 raised (3 merges).

### 3.1 Engagement & habit — 12 items

*Primary lens: engagement-loops. Constraint held throughout: engagement is drawn from prediction fun, accountability, and personalization — never wagering mechanics, urgency, or hot-streak nudges.*

**E1. Pick 'Em Before You Peek** — Tap Over/Under on any call before the model's lean is shown, then get graded side-by-side with the model on reveal.
*Also raised by ux-friction (#7 "Beat the model" pick-before-reveal mode) and predictive-value (#13 grading loop); this is the roadmap's single most-converged idea.*
WHY: The spoiler-masked results and flip-cell Result column stage a perfect guessing moment, but the user is a spectator — the only verb on the board is "sort," and the reveal toggle's tension is spent after one flip (localStorage persists it forever). Committing a pick first converts the replay into a game and makes a weekly cadence self-renewing: new slate, new picks, Tuesday grading. It also teaches calibration honestly — a hit rate near 50% is itself the lesson the how-it-works page preaches.
HOW: v1 fully static: "Your pick" column on the board + pick control on each MarketCard, stored in localStorage keyed `{season}.{week}.{playerId}.{market}`. Once picked, show the model's lean; on reveal, grade both ("You and the model both called UNDER — you both hit"). Board record chip becomes two rows: model 158–98, you 7–3. Guardrails: score is you-vs-model accuracy, never money; no streak-based framing, no urgency timers; copy stays "prediction practice, not a bet slip."
IMPACT 5 | EFFORT M | CATEGORY core-loop

**E2. My Players watchlist** — A star on every board row and player page that pins "My players" to the top of the board.
WHY: The board is 359 calls deep with a "Show 30 more" pager; a casual fan cares about ~8 players. Today a returning visitor re-scrolls and re-filters from scratch every time. Watchlists are the cheapest "reason to come back," and per-player pages, headshots, and receipts already exist to hang them on.
HOW: localStorage array of playerIds; star toggle on board rows, mobile cards, and the player header; a "My players" filter pill next to All/QB/RB/WR/TE in `Board.tsx`. Seeds the 2026 digest (L1) — that's the moment accounts become worth it.
IMPACT 4 | EFFORT S | CATEGORY personalization

**E3. Home team home page** — Pick your NFL team once; your game leads the slate, your players lead the board, the hero card features your QB.
WHY: The data already supports it (team dropdown, team-colored game dots) but nothing remembers the one question every casual walks in with: "what about MY team?" Team identity is the strongest recurring hook in NFL fandom.
HOW: One-tap team picker (grid of existing TeamDot monograms), stored in localStorage; all effects are client-side re-sorts of existing JSON. No backend ever needed.
IMPACT 4 | EFFORT S | CATEGORY personalization

**E4. The Tuesday Grade — weekly recap page** — A single scrollable "how did the model do this week" story: record, best call, worst miss, calibration check, one lesson.
*Complemented by predictive-value #7 (track record page, listed as P6) — recap is the weekly ritual, track record is the season audit; they share pipeline exports.*
WHY: The revealed board already computes 158–98–0 with 33 DNP and every MarketCard writes a result sentence, but this narrative is scattered across 359 rows. The receipts culture is the differentiator and has no destination page, no shareable artifact, no ritual moment. In a live season, Tuesday is the natural second beat (Thursday = new slate, Tuesday = grading).
HOW: v1 static route `/recap` built from `slate.json` at build time: headline record, top-3 strongest hits, the single worst miss with its factor list ("what fooled the model"), strong-calls-only record, and the user's own pick record from E1. Guardrail: misses get equal visual weight to hits — an accountability report, never a "we're hot, get in now" pitch.
IMPACT 5 | EFFORT M | CATEGORY ritual

**E5. Receipts ticker on the home page** — Promote the season-long model record from an 11px corner caption to a first-class hero element.
WHY: The number a casual understands — "158–98 on graded leans, strong calls 85%" — exists in the app but only appears after flipping the toggle, in tiny text. `meta.json` already carries strongCallHitRate per market; the trust-building headline is sitting unrendered.
HOW: Fourth hero tile or slim strip under the replay banner, each term InfoTip'd, linking to /how-it-works and /recap. Guardrail: always render hits and misses as one inseparable unit — never "91% winners!" alone.
IMPACT 3 | EFFORT S | CATEGORY trust-loop

**E6. Per-call reveal (spoiler control, not scratch cards)** — Tap any individual Result cell to flip just that call, keeping the rest of the week unspoiled.
WHY: The flip animation already exists per row but is driven only by the global switch — checking one Josh Allen call spoils all 359 results permanently. Per-call reveal preserves suspense across sessions and pairs with E1 (reveal only after picking).
HOW: Extend RevealContext with a revealed-set (`Set<propKey>`) alongside the global flag, persisted in localStorage. Ethics requirement enforced: a calm flip tied to information the user asked for — no slot-machine easing, no confetti-on-hit asymmetry; hits and misses animate with equal weight.
IMPACT 3 | EFFORT S | CATEGORY core-loop

**E7. Share-worthy call cards (OG images + share button)** — Every player call gets a real og:image and a share action: projection/curve/lean before the game, graded receipt after.
WHY: The hero already renders the ideal artifact (the Jordan Love mini-card), but `generateMetadata` ships no og:image, so shared player links collapse to plain text. Group chats are where prop talk happens; the post-game graded receipt is the most share-worthy variant because it's verifiable.
HOW: Build-time PNGs via satori/@vercel/og for each player+market in two variants (call / graded receipt); Web Share API on mobile with copy-link fallback. Guardrail: cards carry the "reference line, not a sportsbook line" footer; never a book logo or odds.
IMPACT 4 | EFFORT M | CATEGORY shareability

**E8. You vs. the Model season ledger** — A running scoreboard of your picks against the model's, week over week.
WHY: The app already loves longitudinal grading (per-player receipts: Allen 50%, Gibbs 67%). Giving the user the same receipt treatment creates an identity loop ("I test myself against the model weekly") without wagering mechanics.
HOW: v1 aggregates localStorage picks into a `/me` page reusing the Receipts styling. Accounts become genuinely necessary here for cross-device sync. Guardrails: no streak-pressure copy, no leaderboard by default — the rival is the model, not other people's money.
IMPACT 4 | EFFORT M | CATEGORY retention

**E9. Sixty-second first-visit walkthrough** — A dismissible three-beat intro that teaches one real call: projection, strength, then "flip results on this one call."
WHY: A first-time casual lands on jargon fast (naked LeanPill, unlabeled strength bar on mobile), and the aha moment — "they showed me a call, then showed me it was right/wrong" — currently requires self-assembly.
HOW: localStorage `seenIntro` flag; coach-mark sequence anchored to one pre-chosen high-strength call, using the E6 per-call reveal primitive; ends by asking the E2/E3 personalization questions. All static.
IMPACT 4 | EFFORT M | CATEGORY onboarding

**E10. The Time Machine — replay any week 1–13** — A week switcher to rerun the whole experience on earlier 2025 weeks.
WHY: The product is a single frozen week; a visitor who finishes Week 14 (especially after E1) has nothing left to do. Thirteen more weeks is thirteen more sessions of the same loop, and it rehearses the weekly cadence before the 2026 live season exists.
HOW: Pipeline emits `slate_wk{N}.json` + per-player files for weeks 1–13 (the walk-forward backtest already computes these predictions); static routes `/weeks/[n]`; header chip becomes a week dropdown. Pick-em state (E1) is already keyed by week.
IMPACT 3 | EFFORT L | CATEGORY content-depth

**E11. Two-beat weekly digest for the 2026 live season** — Opt-in email/push: Thursday "your slate is ready," Tuesday "the receipts are in."
*(Detailed in §4 Live-season readiness; listed here for completeness of the engagement loop.)*
WHY: The digest is distribution, not new content — Thursday is the personalized board (E2/E3), Tuesday is the recap page (E4).
HOW: Email capture + preferences; weekly job rendering E4's recap. Hard rules: fixed cadence only (never event-triggered "line moving, act NOW"), no sends within game windows, no loss-framed re-engagement, one-tap unsubscribe, hit/miss always reported together, "past accuracy never promises future results" in every send.
IMPACT 4 | EFFORT L | CATEGORY re-engagement

**E12. "Set the line yourself" gut-check on player pages** — Drag a blank slider to where YOU think the line should be, then the model's distribution fades in over your guess.
WHY: The DistributionChart slider is the most delightful interaction in the app but is presented answer-first, anchoring the user before they form an opinion. Inverting one moment creates a Wordle-like intuition test that teaches distribution thinking better than any glossary entry.
HOW: Optional "test your gut" chip on the MarketCard header; records the guess in localStorage; reuses `probOver`/`sliderDomain`/`snap` wholesale. No money, no odds — pure calibration play.
IMPACT 3 | EFFORT S | CATEGORY delight

### 3.2 UX clarity — 13 items

*Primary lens: ux-friction. The trust posture is the product's best feature; every fix protects it.*

**U1. Un-clip the board's column-header tooltips** — The one place a casual can learn what "Strength 81" means renders as an empty sliver.
WHY: Verified programmatically: the STRENGTH header tooltip opens at y=358 inside containers clipping at y=428 (`.card overflow-hidden` > `.overflow-x-auto`, `Board.tsx:299-300`) — 100% clipped. All six header tooltips (Projection, Lean, Strength, Confidence, Result) are unreadable, so the board's core vocabulary is never explained on desktop.
HOW: Render `InfoTip` content in a portal to `document.body` positioned via `getBoundingClientRect`, or add a `dropdown-below` variant for table headers.
IMPACT 5 | EFFORT S | CATEGORY comprehension-bugfix

**U2. Resolve the "green +0.3 but lean UNDER" contradiction — and surface P(over) on the board.**
*Also raised by predictive-value (#6, "P(over) column on the Top Calls board"); merged because the same fix serves both.*
WHY: 12 board rows (James Cook, Jared Goff, David Montgomery…) show the projection beating the line in green while the pill says Under, because P(over) is low even though the mean sits above the line — the casual's first "this thing is broken" moment, with zero reconciliation offered. Separately, "9% to clear 102.5" is more decision-legible than "strength 81," and P(over) is the number every downstream tool (P1–P3) speaks in.
HOW: (a) Color the delta by lean rather than sign and show `overProbAtRef` ("24% to clear") next to the pill — the data is already in every row; (b) add a sortable P(over) column to desktop table and mobile cards, keeping strength as the composite sort; (c) on affected rows, a one-line InfoTip: "The projection is the middle outcome; the odds come from the whole curve."
IMPACT 5 | EFFORT M | CATEGORY comprehension

**U3. Plain-English strength tiers everywhere the naked number appears.**
WHY: Mobile board cards show projection, a bar, and a bare "56" — no label, no tooltip, and no Confidence badge at all on mobile (`Board.tsx:419-448`). How-it-works already defines "strong calls" as 60+ hitting 87–91%.
HOW: Map strength to backtest-justified words: 0–14 "coin flip", 15–39 "slight", 40–59 "solid", 60+ "strong" (chip: "Strong · 81"); add the Confidence badge to mobile cards; on "strong" rows the tooltip may honestly cite "calls this strong hit 87–91% in weeks 1–13" (with n, per M3/M12 honesty rules).
IMPACT 4 | EFFORT S | CATEGORY comprehension

**U4. Make game cards go somewhere (game hub pages).**
*Also raised by engagement-loops (#10, game hub pages) and predictive-value (#9, same-game lens) — flagged independently by three lenses. The correlation-warning layer is tracked separately as P8.*
WHY: `GameCard.tsx:48` uses `card-hover` styling that promises clickability but renders a plain `<article>`. There is no game page and no board filter by game; the #1 casual mental model ("I'm watching this game, what are the calls?") has no path. The data (gameId on every prop, weather chips, kickoff times) is already joined.
HOW: v1 without new pages: clicking a game card scrolls to the board and applies a `gameId` filter (URL query param `/?game=2025_14_CIN_BUF`). v1.5: static `/games/[gameId]` pages (14) grouping that game's props by team, sorted by strength, reusing Board's mobile card component and the game context chips. Kickoff-aware "starts in 2 hours" copy waits for live mode (§4).
IMPACT 4 | EFFORT M | CATEGORY navigation

**U5. Add a next-step flow on the player page.**
WHY: The only exit from a player page is "Back to this week's calls," which also loses board filter state (filters are unpersisted `useState`). For 173 players the browse loop is scroll board → click → scroll back → re-find your place.
HOW: Static v1: a "More from this game" strip (players sharing `gameId`, derivable at build time) plus a "Next top call" link ordered by strength; persist board filters in URL params so the back link restores them.
IMPACT 4 | EFFORT M | CATEGORY navigation

**U6. Label the mobile reveal toggle and keep the replay chip.**
WHY: On <640px the header hides both the "Replay · 2025 Wk 14" chip and the "Show results" text (`Header.tsx:36,62`), leaving an unlabeled eye icon — while spoiler covers instruct users to 'flip "Show results" in the header,' a control by a name they cannot see. Mobile visitors also lose the only replay-mode cue.
HOW: Compact "Results" label next to the icon, or make every spoiler chip itself a toggle button (it sits under the thumb; the copy problem disappears). Slim "Replay Wk 14" text under the logo on mobile.
IMPACT 4 | EFFORT S | CATEGORY mobile-ergonomics

**U7. Fix the revealed record to respect filters, and give the empty state a reset.**
WHY: `Board.tsx:198-211` computes the hit/miss record over all rows, not `filtered` — after filtering to one team the banner still reads "158 hits · 98 misses," so the trust feature itself gives a wrong answer. It also replaces the "N of 359 calls" count. Separately, the empty state (QB + Receptions, a combo the UI allows) offers no way out but manually unwinding four controls.
HOW: Compute the record from `filtered`; render both count and record when revealed; add a "Clear filters" button; optionally hide market options incompatible with the selected position (`meta.markets[].positions` already encodes this).
IMPACT 3 | EFFORT S | CATEGORY trust-accuracy

**U8. Explain DNP and push where they appear — including the #1 call.**
*Overlaps predictive-value #4 (availability risk flag, P4): U8 is the comprehension fix, P4 is the decision-risk fix; ship both.*
WHY: 33 of 359 calls (9%) are DNP, including the top-sorted row (Drake London, strength 81). Revealed cells show "DNP" with only a desktop `title` attribute — nothing on touch — and the glossary defines neither DNP, push, hit, nor miss. No one tells the casual how DNPs affect the advertised hit rates.
HOW: Add DNP and Push to the glossary; tappable InfoTip on board DNP/push marks ("Did not play — call gets no grade and never counts in our record"); pre-reveal, a subtle "availability watch" dot on players whose rest factor flags a recent absence — honest signal, not a spoiler.
IMPACT 3 | EFFORT S | CATEGORY comprehension

**U9. Rebuild the report card table for mobile.**
WHY: On 390px the 5-column table wraps "(we're 3% tighter)" one word per line and pushes the most persuasive column — "Strong calls that hit" — off-screen with no scroll cue. The page's whole argument ("judge us") is amputated on the device most casuals use.
HOW: Below `md`, render each market as a stat card (title + four labeled rows), or drop the baseline column into a footnote. Pure CSS/JSX.
IMPACT 3 | EFFORT M | CATEGORY mobile-ergonomics

**U10. Add player search on the board.**
WHY: No search anywhere in `src/` (grep-verified). The casual's most common entry intent — a specific player from their fantasy team — is served only by position/team filters plus pagination across 359 rows.
HOW: Client-side text input in the Board filter row matching `r.name` (data already fully in memory); on the mobile card list too. Fuzzy match is a nice-to-have.
IMPACT 3 | EFFORT S | CATEGORY navigation

**U11. Make factor headlines agree with their arrows.**
WHY: On Ja'Marr Chase, "Buffalo gives up 177 receiving yards a game — the fewest in the NFL" is tagged +13.7 yds UP; the resolution (recent defensive form outweighs season stats) is buried in the detail line. A casual trusts headline + arrow and concludes the model is confused. Template risk exists pipeline-wide since factor copy is generated.
HOW: In the pipeline's copy generator, when a factor's net direction contradicts its season-stat headline, lead with the net story: "Season stats say stingy, but recent games say beatable — nets out +14 yds." Data regeneration only; `DATA_CONTRACT.md` unchanged.
IMPACT 3 | EFFORT M | CATEGORY comprehension

**U12. Ship a branded not-found page.**
WHY: `/players/9999999` renders the stock Next.js 404 — white background against the dark header, illegible logo, no link home. Shared player links will rot across weeks once the slate changes, making this a real path.
HOW: `src/app/not-found.tsx` with the site shell, "That player isn't on this week's slate," CTAs to the board and how-it-works.
IMPACT 2 | EFFORT S | CATEGORY polish

**U13. Keep the market-card verdict in sync with the dragged line + small hygiene fixes.**
WHY: After moving the slider, the static `prop.verdict` sentence ("9% chance to clear 102.5") coexists and disagrees with the moved-line readout (47.5 / 70%). Same neighborhood: duplicate `id="board"` on two sections (verified), no sort control on mobile (sort lives only in desktop `<th>` buttons), and the Last-10 chart silently skips weeks (bye vs DNP unclear).
HOW: Swap the verdict for a live template when `line !== refLine` ("At your 47.5 line: 70% to clear" — numbers already computed in `MarketCard.tsx`); remove the inner duplicate id; add a compact sort select next to mobile filter pills; render skipped weeks as hollow "out" ticks in `Last10Chart`.
IMPACT 3 | EFFORT M | CATEGORY polish

### 3.3 Model accuracy & calibration — 13 items

*Primary lens: ml-accuracy. All findings verified empirically on `pipeline/data/models/backtest_predictions.csv` (7,628 walk-forward rows). The as-of feature machinery was audited for leakage and is clean.*

**M1. Conformalized quantile regression (CQR) on the exported band** — Fix interval coverage with a provable wrapper, no retraining.
WHY: pass_yds coverage80 = 0.749 with symmetric 12%/12% tail misses; rush_yds 0.778. Simulated split-CQR walk-forward on the actual backtest CSV: pass_yds 0.752 → 0.840, rush_yds 0.775 → 0.804, and it correctly left rec_yds/receptions untouched.
HOW: In `backtest.py`/`export.py`, compute conformity scores `max(p10−y, y−p90)` on a calibration window (2024 pre-launch; expanding 2025/2026 weeks in-season), take the finite-sample 0.80 quantile per market, expand `[p10−q̂, p90+q̂]` (clip at 0), rebuild `_cdf_nodes` so `probCurve`/`overProbAtRef` soften consistently. Use separate lower/upper tail scores to land nearer 0.80. Static JSON pipeline unchanged.
IMPACT 5 | EFFORT S | CATEGORY calibration

**M2. Fix the pass_tds Poisson lambda (use the conditional mean, not the mean/median blend)** — One-line bias fix worth ~5pts of P(over) at every bucket.
WHY: `pass_tds_prob_curve` uses `lam = projection` where `projection = 0.5*(mean + p50)`; the count median drags lambda ~0.15 TD low (mean(y)=1.32 vs lambda 1.17), so predicted over-rates run below actuals in all six calibration buckets. Reconstructed mean-model lambda closes two-thirds of the aggregate bias (0.400 → 0.441 vs actual 0.462).
HOW: In `train.py:pass_tds_prob_curve`, pass the mean-model prediction (or refit pass_tds with `HistGradientBoostingRegressor(loss="poisson")` — log-link, non-negative by construction) as lambda; keep the displayed projection as-is if product prefers the blend. Re-run backtest; check the 0.15/0.35 buckets first.
IMPACT 4 | EFFORT S | CATEGORY bug-fix

**M3. Per-quantile coverage table + proper scoring rules in the backtest report** — Make the evaluation capable of catching degenerate-quantile failures.
*Overlaps predictive-value #5 (P5): M3 fixes the internal report, P5 threads the same honesty into user-facing range copy.*
WHY: The report shows only MAE + coverage80 + strong-call hit; a per-quantile empirical coverage line would have flagged `P(y ≤ p10) = 0.000` for receptions instantly. Pinball losses were computed but are unreported, and strong-call rates on n=21 carry no CI.
HOW: Extend `evaluate_market` to emit per-quantile empirical coverage, mean pinball per quantile (CRPS ≈ 2×avg pinball), Brier for `over_prob` vs `y > ref_line`, and Wilson intervals on strong-call n; print in `print_report`/`write_report`; optionally surface in `/how-it-works` — honest receipts fit the trust positioning and the responsible-engagement constraint (don't advertise 90% hit rates on n=21).
IMPACT 3 | EFFORT S | CATEGORY evaluation

**M4. Add position indicator features (or per-position heads) to the pooled models.**
WHY: `FEATURES` contains no position flag while rush_yds pools QB+RB (utterly different carry distributions) and rec markets pool WR/TE/RB. The model must reverse-engineer position from usage proxies, wasting splits.
HOW: Add `is_qb/is_rb/is_wr/is_te` one-hots to a new `FACTOR_GROUPS["position_role"]` (feeds `explain.py` automatically); compare per-position MAE/pinball on the 2024 holdout before/after. Full per-position models are the fallback; sample sizes favor pooled+flag first.
IMPACT 3 | EFFORT S | CATEGORY features

**M5. Discrete count distribution for receptions (and pass_tds dispersion)** — Replace degenerate p05/p10=0 quantiles with a real PMF.
WHY: receptions' 80% interval is effectively one-sided `[0, p90]` (p05/p10 exactly 0.0 for 100% of rows; coverage 0.890 with the lower tail never missing); star receivers get p10=0 despite empirical P(≤1 catch) = 3.6%. Half-line over-probs for a count should be PMF mass sums, not interpolation through a strictified continuous CDF.
HOW: HGB mean model with `loss="poisson"` for receptions; estimate negative-binomial dispersion globally or per targets-volume bin from 2024 residuals; derive quantiles as NB inverse-CDF and `P(over k+0.5) = 1 − CDF_NB(k)` in `receptions_prob_curve`. Apply the same NB dispersion to pass_tds (with M2's lambda). Exported JSON shape unchanged.
IMPACT 4 | EFFORT M | CATEGORY distributional-model

**M6. Light-touch P(over) shrinkage calibration, fit walk-forward** — Kill the 0.7+ bucket overconfidence without isotonic's noise.
WHY: rush_yds 0.7–1.0 bucket: pred 0.745 vs actual 0.626; rec_yds 0.743 vs 0.649. Weekly isotonic was tested walk-forward: bucket means improve but Brier worsens (0.2382 → 0.2416) — it overfits small weekly calibration sets.
HOW: 2-parameter Platt map `p' = σ(a + b·logit(p))` per market on expanding walk-forward predictions (pool rush+rec if thin); apply in `build_prob_curve` before export. Do M1 first — CQR removes much of this mechanically. Responsible-engagement note: this will reduce the count of 75%+ strong calls shown — **do not compensate by lowering `STRONG_CALL_MIN`**.
IMPACT 3 | EFFORT S | CATEGORY calibration

**M7. QB-quality and team passing-volume features from data already held.**
WHY: `qb_situation` is just `qb_prior_starts`/`qb_unsettled`; a receiver's rec_yds ceiling depends on team passing production, yet no team-pass-yds or QB-form feature exists. rec_yds MAE beats baseline by only 0.85 yds — the cheapest headroom.
HOW: In `features.py`, add `team_pass_yds_l5` (rolling team sum) and the named starter's own `form_mean5` of pass yds (reuse `player_form_events` + the `qb_name` match from `_qb_starts`). Strict as-of joins as elsewhere; add to `qb_situation` group so explain.py picks it up.
IMPACT 3 | EFFORT S | CATEGORY features

**M8. Recency sample-weighting now, weekly refit cadence for the 2026 live season** — Stop treating 2021 like 2025.
*(Refit cadence and CI cron detailed in §4.)*
WHY: Models are trained once on 2021–2024 with uniform weight ("walk-forward" is features-only); league QB pass yds fell ~16 yds/game from 2021 to 2025, and pass_yds coverage was worst in early weeks (0.711 wks 1–4). HGB trains all five markets in seconds — a frozen model is a choice, not a constraint.
HOW: (a) `sample_weight = 0.5**(seasons_ago/h)` in `train_market`, tune h on the 2024 holdout; (b) make the backtest honestly walk-forward by refitting at each week t on all data < t (matches live behavior and feeds the conformal/Platt calibration streams); (c) for 2026, a weekly cron: retrain → backtest-to-date → export JSON → redeploy static site.
IMPACT 3 | EFFORT M | CATEGORY training

**M9. Snap counts + air yards from nflverse** — The two absent usage signals that are free and reliable.
WHY: Current usage features are box-score counts. Air-yards share separates a 6-target deep WR from a 6-target screen back — directly targets rec_yds, the weakest market vs baseline; snap % detects role changes ~2 weeks before a 4-game target window does. Routes/PFF are proprietary — skip them.
HOW: Add nflverse releases to `download.py` (`player_stats`: air_yards, target_share, wopr; `snap_counts`: offense snap %); crosswalk ids via the existing `db_playerids.csv`. New features `air_yards_share_l4`, `adot_l5`, `wopr_l4`, `snap_pct_l3`, as-of joined. Validate id-join coverage ≥95% before trusting.
IMPACT 4 | EFFORT M | CATEGORY data-source

**M10. Injury reports: practice status + teammate-out target redistribution** — Model who's hurt and who inherits the volume.
*Feeds the UI availability flag (P4); live weekly refresh covered in §4.*
WHY: Availability features are backward-looking (`dnp_last_week`, `games_missed_l5`). The model can't see Friday "Questionable" tags, nor that a WR1 being OUT boosts WR2's targets — a first-order driver of prop misses.
HOW: nflverse `injuries` dataset (weekly, pre-game). Features: own status (Q/D/O one-hot, practice-participation trend) and `top_teammate_out` (top-2 `targets_m4` teammate at the position group is O/IR). Strictly pre-kickoff data, as-of by construction. Historical files exist for the 2025 replay; live it joins the weekly refresh.
IMPACT 3 | EFFORT M | CATEGORY data-source

**M11. Quantile-model regularization: early stopping, per-loss depth, log1p tail experiment.**
WHY: `_hgb` uses `early_stopping=False`, 400 iters, and the depth grid is scored only by mean-model MAE — the seven quantile models inherit a depth never validated on pinball loss; out-of-sample band compression (pass_yds both tails ~12%) is the classic signature.
HOW: Time-ordered validation (2024) with pinball-loss early stopping per quantile model; extend the depth probe to score pinball at q=0.10/0.90. A/B fitting yards quantile models on `log1p(y)` and back-transforming (quantiles are equivariant under monotone maps — safe, unlike for the squared-error mean model). Judge by M3's per-quantile coverage + pinball.
IMPACT 2 | EFFORT S | CATEGORY training

**M12. Fit confidence thresholds out-of-sample** — Remove the eval-set circularity behind the strong-call metric.
WHY: `backtest.py:129` fits `calibrate_conf_thresholds` on the same 2025 weeks it scores; confidence feeds strength, and strength ≥ 60 gates the strong-call sample — the headline strong-call hit rates (0.905 on n=21) are selected with hindsight cutoffs, and n=21–74 carries ±10–20pt binomial CIs nowhere reported.
HOW: Compute thresholds from the 2024 holdout (or expanding weeks < t inside M8b's loop), persist, apply unchanged to 2025 eval and the week-14 export; report the (likely small) metric shift honestly in `BACKTEST_REPORT.md`.
IMPACT 2 | EFFORT S | CATEGORY evaluation

**M13. Score the model against archived real sportsbook lines** — The current "hit rate" is measured against the model's own cousin.
*(Also a §4 gate: mandatory before any live-2026 "edge" claims.)*
WHY: `ref_line` is snapped from `form_med5`/`form_season_med` — features the model itself consumes — so `strongCallHitRate` measures beating a self-generated line, not market value.
HOW: One-time batch pull of 2025 closing player-prop lines into `pipeline/data/raw/lines/`; parallel backtest track (coverage/Brier/hit-rate vs real lines where matched; ref-line track for unmatched). Responsible-engagement note: if the real-line hit rate is worse (it will be), publish it anyway — the product's stated value is honesty, not manufactured confidence.
IMPACT 3 | EFFORT M | CATEGORY evaluation

### 3.4 Predictive decision tools — 12 items

*Primary lens: predictive-value. Design principle across the theme: these tools move users toward fewer, better-understood decisions; "no edge" is a first-class outcome, not a failure state.*

**P1. Type YOUR book's line** — Numeric line input next to the slider so users evaluate the line they're actually offered.
WHY: `MarketCard.tsx` has only `<input type="range">` snapped to `refLine + k·lineStep`, so a real book line like 250.5 against a 249.5 ref is literally unreachable. The ref line is also sometimes stale vs the model (Chase rec yds refLine 102.5 sits ABOVE the model's p90; 3 of 359 rows have refLine outside [p10,p90]) — the user's decision input is their book's number.
HOW: Small numeric input beside the slider (any 0.5 increment, clamped to probCurve domain), feeding the existing `probOver()` interpolation; persist per-prop user lines in localStorage; reflect in a `?line=` query param for sharing. Zero pipeline change; ~30 lines.
IMPACT 5 | EFFORT S | CATEGORY line-tools

**P2. Model fair line + alt-line ladder** — The line where the model is 50/50, plus P(over) at ±1–2 steps.
WHY: The dense probCurve (24–51 points per prop) is consumed one line at a time via the slider. The fair line (curve crossing 0.5 ≈ p50) is the single most compressed statement of the model's opinion and is never shown — especially decisive for "no lean" rows like Josh Allen pass yds (50% at 252.5), where a book hanging 245.5 changes everything.
HOW: Compact 5-row ladder on MarketCard computed client-side from `probCurve` via `probOver()`: refLine (or P1's user line) ± 1–2 lineSteps with P(over)/P(under) per rung; a "model fair line: 259.0" chip in the projection block. Pure frontend, existing exports.
IMPACT 5 | EFFORT S | CATEGORY line-tools

**P3. Break-even check (enter your odds)** — User types their price (e.g. −115); see model P(over) at their line vs the break-even probability the price implies.
WHY: The one transform that turns a probability into a decision, and everything needed exists. How-it-works explicitly warns "books shade their numbers… always compare before you act" but gives no tool to do the comparison. "Model 58% vs break-even 52.4% (+5.6 pts)" — or, more often, "model 51% vs 52.4%: no edge" — is the honest, analysis-side answer.
HOW: Optional American-odds input next to P1; implied prob computed client-side; user-typed only — no odds feeds, no integrations. Guardrails: never rank or aggregate "edges" into a bet-more surface; show the calibration caveat (pass-yds 0.55 bucket resolved 47.6%) inline; default the field to empty; style "no edge" as a first-class outcome.
IMPACT 5 | EFFORT M | CATEGORY pricing

**P4. Availability risk flag** — Warn on the board when a player has missed recent weeks instead of letting DNPs top the strength sort.
*Also raised by ux-friction (#9's "availability watch" dot, U8) for the comprehension side; model-side fix is M10.*
WHY: Week 14 revealed shows 33 DNP calls, and the #1 and #9 strength rows (Drake London 81, Garrett Wilson 62, both "high" confidence) were DNPs. The signal exists as buried prose (Chase's rest factor: "Missed 1 of the last 5 weeks") but nothing structured reaches the board, whose sort actively promotes these rows.
HOW: v1 without pipeline change: derive missed weeks at build time from gaps in `recentGames[].week` vs `gamesPlayed2025`, attach `missedRecent` to slate rows, render an amber "missed 2 of last 5" chip and demote/asterisk such rows in the default sort. Proper fix: pipeline exports `availability: {status, practiceNotes}` from nflverse injury reports (M10). Still static.
IMPACT 4 | EFFORT M | CATEGORY risk

**P5. Per-market honest range labels** — Replace the generic "8 times out of 10" range copy with each market's actual backtest coverage.
*Pairs with M3 (report-side honesty); this is the user-facing half.*
WHY: The MarketCard tooltip and glossary promise the p10–p90 band catches the real number "about 8 times out of 10," but `meta.backtest.byMarket.coverage80` says 74.9% for pass yds and 89% for receptions — the exact data is already shipped to the client. Also fixes a trust inconsistency with the how-it-works report card, which prints the true numbers.
HOW: Thread `coverage80` into the range InfoTip per market: "in this season's backtest this range caught the real number 75% of the time." One prop drill through `getMeta()`. (Once M1 lands, these labels update automatically to the improved coverage — trust compounding in action.)
IMPACT 3 | EFFORT S | CATEGORY trust

**P6. Track record page (by week and by strength band)** — A standing `/track-record`: weekly hit rate, MAE trend, hit rate by strength/confidence bucket with n.
*Complements engagement-loops #4 (E4 Tuesday recap = the ritual; this = the season audit) and #5 (E5 hero ticker links here).*
WHY: The accountability story is the moat, but season-level evidence lives only in how-it-works prose and per-player receipt lists. Week-level history can't be honestly built client-side: `modelHistory` is capped at 8 rows/player and recency-skewed (1,372 rows total; week 1 has 8, week 13 has 325). The backtest already walks weeks 1–13 and grades every row — the aggregation exists, it's just not exported.
HOW: New pipeline export `backtest.byWeek[market] = [{week, n, hitRate, mae, strongN, strongHitRate}]` in `meta.json` (contract change per DATA_CONTRACT rules); static page reusing `CalibrationChart` patterns — weekly hit-rate line with n labels, strength-band bars, losing weeks as prominent as winning ones. Guardrails: present as audit, never momentum; no streak counters; always print n (strength ≥60 hit 90.5% on pass yds but n=21).
IMPACT 4 | EFFORT M | CATEGORY accountability

**P7. "What would flip this call"** — For every lean, state the flip line; for low-confidence calls, state what evidence is missing.
WHY: 47 slate rows are low confidence and 76 neutral, but the UI's only uncertainty language is a static `confidenceReason` string (identical verbatim across all three Allen cards). The probCurve makes the flip point computable today, and factors give the levers: Allen's pass yds carries a −29.4 wind factor — if the forecast changes, so does the read.
HOW: Frontend-only v1: compute flip line from `probCurve` ("this lean survives until the line moves past 259.0"); for low-confidence props, template a sentence from the largest-|impact| volatile factor group (weather, qb_situation, rest_schedule): "watch the wind forecast — it's worth ±29 yds here." Later: pipeline exports per-factor `volatility: stable|could_change`.
IMPACT 4 | EFFORT M | CATEGORY uncertainty

**P8. Same-game correlation warnings** — On game pages, flag correlated pairs of calls.
*Builds on the game hub pages (U4, also raised by engagement-loops #10); this is the decision-value layer.*
WHY: Casual bettors' favorite instrument is the same-game parlay, and the app currently lets them read "Burrow over pass yds" and "Chase over rec yds" as independent 58%/60% events when they share one game script. Warning about this is genuine insight no book volunteers.
HOW: On `/games/[gameId]`, rule-based chips: same-team QB pass yds ↔ WR/TE rec markets "tend to move together"; QB pass volume ↔ same-team RB rush yds "tend to offset"; pace/total context from `vegasTotal`. Real numbers need a small pipeline export — `correlations.json`, empirical residual correlations by position-pair × market from the 2021–2024 training boxscores. No joint-probability math in v1 (don't fake precision); qualitative flags only.
IMPACT 4 | EFFORT M | CATEGORY correlation

**P9. "Model vs the player's norm" surfacing** — A second discovery axis: where the projection departs most from the player's own season average.
WHY: Strength is the board's only ranking, its median is 16, and only 10 of 359 rows clear 60 — discovery dies after the first screen. The genuinely interesting contrarian reads are model-vs-baseline: Chase projected 73.0 rec yds against an 88.3 season average (−17%), with the "why" already written in his factors. `seasonAvgs` exists in every player file but never reaches the board.
HOW: Build-time join in the home page's server component: attach `seasonAvg` and `pctVsAvg` to each slate row; "vs norm" sortable column and a "Biggest departures" filter pill. No pipeline change; DATA_CONTRACT untouched.
IMPACT 3 | EFFORT S | CATEGORY discovery

**P10. Boom/bust volatility tag** — Label each prop steady / volatile / upside-skewed from its own quantiles.
WHY: The quantiles encode shape the UI flattens into one "range" string. Tail asymmetry (p90−p50)/(p50−p10) has slate median 1.19 and 90th percentile 2.01 — receiving markets are strongly right-skewed (Chase: p10 27 vs p90 100.8). An over on a skewed market and an under on a tight one are different kinds of decisions.
HOW: Client-side classification from `quantiles`: relative width buckets → "steady"/"swingy"; asymmetry >1.5 → "upside tail" badge with one plain-English sentence ("big games do the heavy lifting here — the median is lower than the average"). MarketCard header + optional board chip. Data fully exported already.
IMPACT 3 | EFFORT S | CATEGORY volatility

**P11. Week-over-week "what changed"** — On each MarketCard, the model's previous call on this player-market and the projection delta.
WHY: `modelHistory` already stores prior weeks' projection/line/lean per market (Chase rec yds: wk13 69.9 → wk14 73.0) but is only rendered as a flat receipts list at page bottom, disconnected from the current call. "The model moved up 3.1 on him since last week" is the context a returning user actually wants.
HOW: v1 frontend-only: pull the newest matching-market `modelHistory` row, render a one-line delta chip ("last week: proj 69.9, leaned under 93.5 — missed") above the factors. Factor-level "why it moved" diffs need a per-week factor snapshot export — defer.
IMPACT 3 | EFFORT S | CATEGORY context

**P12. "My card" research slip with post-reveal self-grade** — Pin calls into a local card, see its aggregate risk profile, then grade it against the replay.
*Overlaps engagement-loops #1/#8 (E1 pick-em, E8 ledger): E1 is the per-call game; this is the multi-leg research surface where P4's availability flags and P8's correlation warnings become actionable.*
WHY: Committing to picks before revealing is the natural game loop for the replay, and the slip is where risk tooling pays off ("3 of your 5 legs are in one game; 1 player is an availability risk"). Everything needed (props, results, probCurves) is already client-side.
HOW: localStorage array of `{playerId, market, line, side}`; slide-over panel summarizing legs with model P at each chosen line, confidence mix, correlation/availability flags; after reveal, a graded card with per-leg hit/miss/DNP. Guardrails are load-bearing: no stake fields, no payout math, no streak tracking, no "run it back" prompt after a losing card, neutral grading copy for wins and losses alike.
IMPACT 4 | EFFORT L | CATEGORY portfolio

---

## 4. 2026 live-season readiness

Everything below only matters (or only fully pays off) once weekly live data flows. Build order matters: the pipeline items gate the product items.

1. **Weekly retrain + redeploy cadence (M8b/M8c — ml-accuracy).** Refit each week on all data < t; weekly cron: retrain → backtest-to-date → export JSON → redeploy the static site. Still no backend or accounts — just CI. This is the substrate for everything else in this section, and it feeds the CQR (M1) and Platt (M6) layers their expanding in-season calibration windows.
2. **Live injury/practice-status feed (M10 model-side, P4 proper fix — ml-accuracy, predictive-value).** Friday Q/D/O tags and teammate-out redistribution join the weekly refresh; the board's availability chip switches from the inferred `missedRecent` heuristic to the exported `availability` object.
3. **Real sportsbook line benchmarking (M13 — ml-accuracy).** Mandatory gate before any live-2026 "edge" language anywhere in the product. If the real-line hit rate is worse than the ref-line rate, publish it anyway.
4. **Two-beat weekly digest (E11 — engagement-loops).** Thursday "your slate is ready" (watchlist + team, from E2/E3) and Tuesday "the receipts are in" (E4's recap + your E1 pick grade). Fixed cadence only; no event-triggered sends; no sends inside game windows; hit/miss always together; "past accuracy never promises future results" in every send. This is also the clean trigger point for accounts (email capture, cross-device sync of picks/watchlist).
5. **Weekly regeneration of the recap and track-record pages (E4, P6).** In replay mode they are evergreen proof; live, `/recap` regenerates weekly and becomes the Tuesday email body, and `/track-record` accumulates the season audit.
6. **Kickoff-aware game hub copy (U4/E10-adjacent — ux-friction, engagement-loops).** "Starts in 2 hours" ordering and copy on game pages is explicitly deferred to live mode.
7. **Pick-em becomes a true weekly ritual (E1/E8).** The localStorage key schema (`{season}.{week}.{playerId}.{market}`) is already live-ready; the season ledger's week-over-week framing only becomes meaningful with real consecutive weeks.
8. **Dress rehearsal before kickoff: the Time Machine (E10 — engagement-loops).** Weeks 1–13 replay is pre-live content, but it exists to rehearse the weekly cadence (and stress-test multi-week exports) before real Thursdays arrive — schedule it in the offseason.

---

## 5. Deliberately rejected

Ideas that brushed the responsible-gambling constraint during review, and why they were cut. All four lenses independently converged on the same line: engagement comes from prediction fun, accountability, and personalization — never from wagering mechanics. This section exists so these stay cut.

| Rejected idea | Raised/considered by | Why it was cut |
|---|---|---|
| User hot-streak amplification ("you're 5-0, ride it") | engagement-loops | Converts self-testing into confidence inflation — the classic on-ramp to overbetting. The rival is the model; streaks are never a prompt. |
| Model hot-streak framing ("the model is hot — get in now") | engagement-loops, ux-friction, predictive-value | Momentum framing on accuracy data is a bet-more nudge. The model's record ships only as an audit with misses co-equal (E5, E4, P6 all carry this guardrail). |
| Urgency/scarcity mechanics ("lines move soon!", scarcity framing on strong calls, event-triggered "line moving, act NOW" pushes) | engagement-loops, ux-friction | Manufactured time pressure is a dark pattern regardless of surface. Digest is fixed-cadence only; no sends inside game windows. |
| Slot/scratch-card reveal styling (variable-reward easing, confetti-on-hit asymmetry) | engagement-loops | Reveal stays a calm spoiler control tied to information the user asked for; hits and misses animate with equal weight (E6 kept only with this reframe). |
| Any deposit, bet-slip, wager, or parlay-builder integration | engagement-loops, ux-friction, predictive-value | Out of category entirely. P12's "card" is a research slip: no stakes, no payout math. P3 takes user-typed odds only — no book feeds, no deep links. |
| Loss-framed re-engagement ("win it back") and loss-recovery nudges after revealed misses | engagement-loops, ux-friction | Loss-chasing is the core harm pattern. Losing weeks/cards get neutral copy and equal visual weight; no "run it back" prompt (P12 guardrail). |
| Streak counters and streak-pressure copy ("don't break your streak!") | engagement-loops, predictive-value | Duolingo mechanics applied to betting-adjacent behavior create compulsion, not calibration. Season ledger (E8) tracks accuracy, never streaks. |
| Public leaderboards by default | engagement-loops | Social comparison escalates risk-taking. Cut from E8; at most an opt-in percentile vs the model, never vs other people's money. |
| Ranking or aggregating "edges" into a bet-more surface | predictive-value | P3 stays per-prop, defaults empty, and styles "no edge" as a first-class outcome; there is deliberately no "today's best edges" list. |
| Advertising strong-call hit rates without sample size ("91% winners!") | ml-accuracy, engagement-loops, predictive-value | 90%+ on n=21 is statistically flattering and behaviorally dangerous. Every hit-rate surface must print n (Wilson CIs in the report, per M3/M12); hits and misses render as one inseparable unit. |
| Lowering `STRONG_CALL_MIN` to preserve the count of 75%+ calls after calibration shrink | ml-accuracy | M1/M6 will honestly reduce displayed certainty; compensating by loosening the tier definition would manufacture confidence the model no longer claims. Explicitly banned in M6. |
| Fake precision in parlay math (joint probabilities on correlated legs) | predictive-value | P8 ships qualitative correlation flags only in v1 — inventing joint-probability numbers would dress guesswork as quant rigor on the highest-risk bet type. |

**Kept-with-reframe notes (head-of-product enforcement pass):** U8's pre-reveal "availability watch" dot was kept because it is an honest risk disclosure, not a spoiler or a tease. E1/E8/P12 were kept because the graded rival is the model and the currency is accuracy, never money. E7's share cards were kept with the "reference line, not a sportsbook line" footer and a ban on book logos/odds. Nothing in the Top 10 required reframing beyond guardrails already specified by the source lenses.

---

*Item counts: Engagement & habit 12 · UX clarity 13 · Model accuracy & calibration 13 · Predictive decision tools 12 — 50 deduplicated items from 53 raised (merges: ux-friction #7 → E1; predictive-value #6 → U2; engagement-loops #10 → U4).*
