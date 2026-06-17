# Handoff: WM 2026 Predictor — Score Tip Improvements

**Generated**: 2026-06-17
**Branch**: main (up to date with origin)
**Status**: Ready for Review / In Progress (next: push to GitHub Pages)

## Goal

Win the company Kicktipp round by improving exact score predictions. The model was restructured to use a dual-lambda system (conservative lambdas for win/draw/loss probabilities, expressive lambdas for score tip selection) that was grid-search validated to improve Kicktipp points by 17% on completed WM 2026 matches.

## Completed

- [x] `details.html` — two-tab page: "Vergangene Tipps" (completed, grouped by date desc) + "Alle Vorhersagen" (pending, grouped by broadcast date asc)
- [x] 6 AM broadcast day boundary — matches at 01:00 local show under previous evening's date
- [x] XSS fixes — all JSON fields escaped via `esc()`, `onclick` replaced with `data-mid` event delegation
- [x] Dual-lambda score tip system — `TIP_DAMPENING=0.3` + `GOALS_SCALE=1.5` (grid-search validated: 28/80 Kicktipp pts vs 24/80 baseline)
- [x] Grid-search infrastructure — `classify_score()`, `evaluate_wm2026_scores()`, `score_grid_search()`, `--score-grid` flag in `backtest.py`
- [x] Tip composition section in detail view — shows λ Modell vs λ Tipp with bars + expected goal diff → chosen tip
- [x] Lambda fields stored in `predictions.json` — `explanation_factors.{prob,tip}_lambda_{a,b}`
- [x] Flag fixes — 12 teams had `🏳` fallback (Algeria, Bosnia, Cape Verde, Congo DR, Curaçao, Czechia, Ghana, Haiti, Norway, Paraguay, Sweden, Uzbekistan); patched in `fixtures.json` + `bootstrap_fixtures.py`
- [x] `.editorconfig` — LF line endings for Rider on Windows

## Not Yet Done

- [ ] Push to GitHub Pages (`git push` — Actions deploy automatically)
- [ ] Bookmaker `score_odds` not yet used for tip selection — currently display-only in the detail view; could blend bookmaker exact-score probabilities into tip-lambda selection
- [ ] Over/Under market from Odds API not yet fetched — would calibrate total expected goals
- [ ] 3 failing unit tests in `tests/test_data_fetcher.py` (pre-existing bug, see Warnings)

## Failed Approaches (Don't Repeat These)

**Simple `round(lam_a):round(lam_b)` for score tip:**
With `POISSON_DAMPENING=0.8`, lambdas compress to ~0.5–1.7. `round(1.73)=2`, `round(0.55)=1` → always tips 2:1 or 1:0. The spread is too narrow to produce 2:0 or 3:1. Fix: use a second lambda pair with `TIP_DAMPENING=0.3` (less dampened = wider spread), then pick the most probable score in the probability matrix that has the expected goal difference.

**`POISSON_DAMPENING` as single parameter for both probs and tip:**
Lowering the main dampening to improve score margins breaks win/draw/loss accuracy (model overtips upsets). The separation into two lambda systems (prob-λ stays at 0.8, tip-λ uses 0.3 × 1.5 scale) solves this.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `TIP_DAMPENING=0.3`, `GOALS_SCALE=1.5` | Grid-search on 20 completed WM 2026 matches; best Kicktipp pts (28/80 = 35%) |
| Tip selected from probability matrix at computed `exp_diff` | Keeps candidate scores probabilistically consistent — picks highest P(score) at the expected goal diff |
| `score_odds` display-only (not used for tip) | Blending bookmaker exact-score P into tip-lambda selection not yet implemented |
| Flags patched directly in `fixtures.json` | `bootstrap_fixtures.py` only runs once at init; flags must live in the JSON to survive across runs |
| Broadcast day = local calendar date minus 6 hours | Matches at 01:00 local "belong" to yesterday's viewing slot |

## Current State

**Working**: All 72 WM 2026 fixtures, 52 pending with tips, 20 completed with accuracy tracking. Detail modal shows tip composition (dual-lambda breakdown). All flags correct. GitHub Pages at `https://tyrabite.github.io/WmPredictor/`.

**Uncommitted Changes**: Only file-mode drifts on `src/model.py` and `data/form_cache.json` — no content changes, safe to ignore.

## Files to Know

| File | Why It Matters |
|------|----------------|
| `src/model.py` | Dual-lambda system; `POISSON_DAMPENING`, `TIP_DAMPENING`, `GOALS_SCALE` constants; `PredictionResult` dataclass with lambda fields |
| `src/backtest.py` | `score_grid_search()`, `evaluate_wm2026_scores()`, `classify_score()` — use `--score-grid` to re-validate |
| `src/update_predictions.py` | Stores `prob_lambda_{a,b}` and `tip_lambda_{a,b}` in `explanation_factors` |
| `src/bootstrap_fixtures.py` | `FLAG` dict — add new team name variants here when API returns unexpected names |
| `data/fixtures.json` | Source of truth for team names and flags; flags stored here (not re-fetched from API) |
| `docs/index.html` | Main GitHub Pages app; `renderDetail()` shows tip composition section |
| `docs/details.html` | Two-tab view; same `renderDetail()` logic as index.html — **must be kept in sync manually** |
| `docs/predictions.json` | Generated output; re-run `python src/update_predictions.py` after any model change |

## Code Context

**Dual-lambda system** (`src/model.py`):
```python
POISSON_DAMPENING = 0.8   # for win/draw/loss probability matrix
TIP_DAMPENING     = 0.3   # for score tip selection (less dampened = wider margins)
GOALS_SCALE       = 1.5   # multiplies both tip-lambdas (shifts toward higher-scoring tips)

# In _poisson_probs() — returns 9-tuple:
# p_win, p_draw, p_loss, top5, all_results, lam_a_tip, lam_b_tip, lam_a_prob, lam_b_prob
d = 1.0 - POISSON_DAMPENING
lam_a = exp(base + atk_a*d - def_b*d) * elo_scale   # probability matrix lambdas
lam_b = exp(base + atk_b*d - def_a*d) / elo_scale

d_tip = 1.0 - TIP_DAMPENING
lam_a_tip = exp(base + atk_a*d_tip - def_b*d_tip) * elo_scale * GOALS_SCALE
lam_b_tip = exp(base + atk_b*d_tip - def_a*d_tip) / elo_scale * GOALS_SCALE

# In predict() — tip selection:
raw_diff = lam_a_tip - lam_b_tip
if p_a wins:   exp_diff = max(1, round(raw_diff))
elif p_b wins: exp_diff = min(-1, round(raw_diff))
else:          exp_diff = 0
# picks highest-prob score in probability matrix with exactly exp_diff goal difference
```

**PredictionResult** (`src/model.py`):
```python
@dataclass
class PredictionResult:
    prob_a: float; prob_draw: float; prob_b: float
    top_results: list[tuple[str, float]] = field(default_factory=list)
    tip: str = ""
    prob_lambda_a: float = 0.0; prob_lambda_b: float = 0.0
    tip_lambda_a: float = 0.0;  tip_lambda_b: float = 0.0
```

**predictions.json shape** (pending match, abbreviated):
```json
{
  "match_id": "A1", "team_a": "Portugal", "flag_a": "🇵🇹",
  "tip": "2:0", "prob_a": 58.2, "prob_draw": 27.8, "prob_b": 14.0,
  "top_results": [["1:0", 14.2], ["0:0", 10.1]],
  "score_odds": {"2:0": 12.5, "1:0": 18.3},
  "explanation_factors": {
    "elo_a": 2048, "elo_b": 1412,
    "prob_lambda_a": 1.503, "prob_lambda_b": 0.633,
    "tip_lambda_a": 3.032,  "tip_lambda_b": 0.865
  }
}
```

Note: `prob_a/draw/b` stored as **0–100** (not 0–1).

**Broadcast day helper** (duplicated in both HTML files):
```javascript
const _SIX_H = 6 * 60 * 60 * 1000;
function broadcastDateOf(dt) { return new Date(dt.getTime() - _SIX_H).toLocaleDateString("en-CA"); }
function pendingBroadcastDate(m) { return m.kickoff_utc ? broadcastDateOf(new Date(m.kickoff_utc)) : m.date; }
```

**Tip composition section** in `renderDetail()` (both HTML files — keep in sync):
```javascript
if (ef.tip_lambda_a != null && ef.prob_lambda_a != null) {
  const rawDiff = ef.tip_lambda_a - ef.tip_lambda_b;
  const sign = rawDiff >= 0 ? '+' : '';
  // renders: factorRow("λ Modell (D=0.8)", ...) + factorRow("λ Tipp (D=0.3, ×1.5)", ...)
  // + <div class="tip-derivation">Erw. Tordiff: <strong>+2.2</strong> → Tipp: 2:0</div>
}
```

## Resume Instructions

1. Activate venv: `source .venv/bin/activate` (Linux) or `.venv\Scripts\activate` (Windows)

2. Verify model state:
   ```bash
   python src/backtest.py --score-grid
   ```
   Expected: baseline 24/80 pts, best grid `tip_dampening=0.3, goals_scale=1.5` → 28/80 pts

3. After any model change, regenerate predictions:
   ```bash
   python src/update_predictions.py
   ```
   Expected: `✅ 52 ausstehende Spiele → docs/predictions.json`

4. Push to publish to GitHub Pages:
   ```bash
   git push
   ```

## Setup Required

- `.env` with `FOOTBALL_DATA_KEY` (required) and `ODDS_API_KEY` (optional — without it, bookmaker odds default to 40%/25%/35% and `score_odds` is empty)
- Python 3.11+, `pip install -r requirements.txt`
- Git identity for commits: `TyraBite / mcnt94@googlemail.com` — **never add Co-Authored-By lines**

## Warnings

**3 failing tests** (`tests/test_data_fetcher.py`): Tests patch `data_fetcher.requests.get` but `data_fetcher.py` uses `_session().get()` (a `requests.Session` with retry adapter). Mock target is wrong so real HTTP calls go through, hitting example.com → 404. Fix: patch `requests.Session.get` or mock `data_fetcher._session`. Left unfixed per user preference (no test-only API changes).

**`renderDetail()` duplicated** in `index.html` and `details.html` — changes to one must be manually mirrored to the other. No shared JS file.

**`form_cache.json` always dirty** — `update_predictions.py` calls `form_tracker.update_all()` which rewrites the file on every run. Intentional — GitHub Action commits fresh form data after each matchday.

**File mode drift** (644→755) on WSL for files under `/workspace` — cosmetic. Can ignore or set `git config core.fileMode false`.

**`score_odds` in predictions.json** is a dict keyed by score string (e.g. `"2:1": 8.5`) representing bookmaker implied probability in %. Stored for display only — not used in tip selection.
