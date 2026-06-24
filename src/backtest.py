#!/usr/bin/env python3
"""
Backtesting framework for WM predictor model.

Evaluates model against:
  - WM 2026 completed matches (out-of-sample)
  - WM 2022 matches (in-sample for Poisson, but shows generalization)
  - Grid search over key parameters

Usage:
  python src/backtest.py               # verbose evaluation with current params
  python src/backtest.py --grid        # full parameter grid search
  python src/backtest.py --hist 2022   # historical evaluation from given season
"""
import sys, json, argparse, pickle
import numpy as np
from scipy.stats import poisson

sys.path.insert(0, 'src')
from klement import FIFA_RANKING
from features import ODDS_NAME_MAP, ELO_NAME_MAP

with open('data/elo_ratings.json') as f:
    ELO_RATINGS = json.load(f)

with open('data/model_poisson.json') as f:
    POISSON_PARAMS = json.load(f)
with open('data/model_xgb.pkl', 'rb') as f:
    XGB_MODEL = pickle.load(f)

# Normalize fixture team names to match Poisson model team names
POISSON_NAME_MAP = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Czechia": "Czech Republic",
    "United States": "United States",  # already correct in model
    "Korea Republic": "South Korea",
    "Cote d'Ivoire": "Ivory Coast",
    "Cape Verde Islands": "Cape Verde",   # not in model, but normalize for future
}

# WM 2026 host nations benefit from crowd support
WM2026_HOSTS = {'United States', 'USA', 'Canada', 'Mexico'}

# Extended FIFA rankings covering all WM 2026 teams that were missing
# Sources: FIFA World Ranking 2025 (approximate)
FIFA_RANKING_EXTENDED = {
    **FIFA_RANKING,
    # Europe
    "Sweden": 17,
    "Albania": 65,
    "Georgia": 75,
    "Slovenia": 57,
    "Hungary": 24,  # already in dict but verify
    # Africa
    "South Africa": 58,
    "Cape Verde": 77,      # ODDS_NAME_MAP maps "Cape Verde Islands" -> "Cape Verde"
    "Mali": 54,
    "Algeria": 40,
    "Ghana": 60,
    # Americas
    "Bolivia": 85,
    "Honduras": 80,
    "Jamaica": 55,
    "Panama": 72,
    "Costa Rica": 70,
    "Cuba": 100,
    # Asia
    "Uzbekistan": 69,
    "Iraq": 68,
    "Jordan": 40,  # already in dict
    # Oceania / Other
    "New Zealand": 48,  # already in dict
    # Teams in WM2026 with no FIFA ranking (estimated)
    "Haiti": 96,
    "Bosnia-Herzegovina": 60,  # fixtures use this spelling
    "Bosnia & Herzegovina": 60,  # ODDS_NAME_MAP normalizes to this
    "Czechia": 33,         # same as Czech Republic (already via ODDS_NAME_MAP)
    "Curaçao": 130,
    "Congo DR": 47,        # already in dict as DR Congo?
}


_XGB_CACHE: dict = {}


def _warmup_xgb_cache(dampening_vals: list) -> None:
    """Precompute XGBoost proba for all (match, dampening) combos in one batch call per dampening."""
    import json as _json
    with open('data/fixtures.json') as f:
        fx_pairs = [(m['team_a'], m['team_b']) for m in _json.load(f) if m.get('status') == 'completed']
    with open('data/historical_matches.json') as f:
        hist_pairs = [(m['team_a'], m['team_b']) for m in _json.load(f)]
    all_pairs = list({p: None for p in fx_pairs + hist_pairs})  # deduplicate preserving order

    for damp in dampening_vals:
        d = 1.0 - damp
        feats = []
        for ta, tb in all_pairs:
            ta2 = POISSON_NAME_MAP.get(ta, ta)
            tb2 = POISSON_NAME_MAP.get(tb, tb)
            a = POISSON_PARAMS.get(ta2, POISSON_PARAMS.get(ta, {'attack': 0, 'defense': 0}))
            b = POISSON_PARAMS.get(tb2, POISSON_PARAMS.get(tb, {'attack': 0, 'defense': 0}))
            feats.append([0, 0.5, 0.5, 0.75, 0.75,
                          a['attack'] * d, a['defense'] * d,
                          b['attack'] * d, b['defense'] * d,
                          0.65, 0.65, 0.5, 0.4, 0.25, 0.35])
        X = np.array(feats)
        probs = XGB_MODEL.predict_proba(X)
        for (ta, tb), proba in zip(all_pairs, probs):
            _XGB_CACHE[(ta, tb, round(damp, 6))] = proba


def get_rank(team: str, extended: bool = True) -> int:
    """Get FIFA ranking with name normalization. Lower = better."""
    ranking = FIFA_RANKING_EXTENDED if extended else FIFA_RANKING
    normalized = ODDS_NAME_MAP.get(team, team)
    r = ranking.get(normalized) or ranking.get(team)
    return r if r is not None else 55  # conservative default for unknown teams


def get_elo(team: str) -> float:
    """Get international Elo rating (from martj42 dataset). Default 1500."""
    normalized = ELO_NAME_MAP.get(team, team)
    return ELO_RATINGS.get(normalized) or ELO_RATINGS.get(team) or 1500.0


def _xgb_proba(team_a: str, team_b: str, dampening: float) -> np.ndarray:
    """XGBoost only depends on (team_a, team_b, dampening) — cache to avoid 400ms/call overhead."""
    key = (team_a, team_b, round(dampening, 6))
    if key not in _XGB_CACHE:
        base = POISSON_PARAMS.get('base_rate', np.log(1.2))
        ta = POISSON_NAME_MAP.get(team_a, team_a)
        tb = POISSON_NAME_MAP.get(team_b, team_b)
        a_raw = POISSON_PARAMS.get(ta, POISSON_PARAMS.get(team_a, {'attack': 0, 'defense': 0}))
        b_raw = POISSON_PARAMS.get(tb, POISSON_PARAMS.get(team_b, {'attack': 0, 'defense': 0}))
        d = 1.0 - dampening
        feat = np.array([[0, 0.5, 0.5, 0.75, 0.75,
                          a_raw['attack'] * d, a_raw['defense'] * d,
                          b_raw['attack'] * d, b_raw['defense'] * d,
                          0.65, 0.65, 0.5, 0.4, 0.25, 0.35]])
        _XGB_CACHE[key] = XGB_MODEL.predict_proba(feat)[0]
    return _XGB_CACHE[key]


def predict(team_a: str, team_b: str,
            elo_factor: float = 0.5,
            poisson_weight: float = 0.85,
            host_bonus: float = 0.0,
            draw_boost: float = 0.0,
            poisson_dampening: float = 0.5,
            tip_dampening: float = 0.3,
            goals_scale: float = 1.0,
            score_odds_blend: float = 0.0,
            score_odds: dict | None = None,
            **_kwargs) -> tuple[str, float, float, float, str]:
    """
    Predict match tendency + score tip. Returns (tendency, p_a, p_draw, p_b, tip).
    Uses tip-lambda Poisson matrix filtered by win direction (no exp_diff rounding bug).
    """
    base = POISSON_PARAMS.get('base_rate', np.log(1.2))
    ta = POISSON_NAME_MAP.get(team_a, team_a)
    tb = POISSON_NAME_MAP.get(team_b, team_b)
    a_raw = POISSON_PARAMS.get(ta, POISSON_PARAMS.get(team_a, {'attack': 0, 'defense': 0}))
    b_raw = POISSON_PARAMS.get(tb, POISSON_PARAMS.get(team_b, {'attack': 0, 'defense': 0}))
    d = 1.0 - poisson_dampening
    a = {'attack': a_raw['attack'] * d, 'defense': a_raw['defense'] * d}
    b = {'attack': b_raw['attack'] * d, 'defense': b_raw['defense'] * d}

    lam_a = np.exp(base + a['attack'] - b['defense'])
    lam_b = np.exp(base + b['attack'] - a['defense'])

    elo_scale = 1.0
    if elo_factor > 0:
        elo_a = get_elo(team_a)
        elo_b = get_elo(team_b)
        if elo_a != elo_b:
            p_elo_a = 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))
            elo_scale = (2.0 * p_elo_a) ** elo_factor
            lam_a *= elo_scale
            lam_b /= elo_scale

    if host_bonus > 0:
        if team_a in WM2026_HOSTS:
            lam_a *= (1 + host_bonus)
        if team_b in WM2026_HOSTS:
            lam_b *= (1 + host_bonus)

    max_goals = 7
    g = np.arange(max_goals)
    pa = poisson.pmf(g, max(lam_a, 0.01))
    pb = poisson.pmf(g, max(lam_b, 0.01))
    mat = np.outer(pa, pb)
    mat /= mat.sum()

    pw = float(np.tril(mat, -1).sum())
    pd_ = float(np.diag(mat).sum())
    pl = float(np.triu(mat, 1).sum())

    xgb = _xgb_proba(team_a, team_b, poisson_dampening)

    p_a = poisson_weight * pw + (1 - poisson_weight) * xgb[0]
    p_d = poisson_weight * pd_ + (1 - poisson_weight) * xgb[1]
    p_b = poisson_weight * pl + (1 - poisson_weight) * xgb[2]

    if draw_boost > 0:
        p_d *= (1 + draw_boost)

    total = p_a + p_d + p_b
    p_a, p_d, p_b = p_a / total, p_d / total, p_b / total

    tendency = ('win' if p_a >= p_d and p_a >= p_b else
                'loss' if p_b >= p_d and p_b >= p_a else 'draw')

    # Tip selection: tip-lambda Poisson matrix, filtered by win direction
    # (no exp_diff rounding — considers absolute goal counts)
    d_tip = 1.0 - tip_dampening
    lam_a_tip = np.exp(base + a_raw['attack'] * d_tip - b_raw['defense'] * d_tip) * elo_scale * goals_scale
    lam_b_tip = np.exp(base + b_raw['attack'] * d_tip - a_raw['defense'] * d_tip) / elo_scale * goals_scale

    pa_t = poisson.pmf(g, max(lam_a_tip, 0.01))
    pb_t = poisson.pmf(g, max(lam_b_tip, 0.01))
    mat_t = np.outer(pa_t, pb_t)
    mat_t /= mat_t.sum()

    tip_scored = {f"{i}:{j}": float(mat_t[i, j])
                  for i in range(max_goals) for j in range(max_goals)}

    if score_odds_blend > 0 and score_odds:
        for s, pct in score_odds.items():
            if s in tip_scored:
                tip_scored[s] = ((1 - score_odds_blend) * tip_scored[s]
                                 + score_odds_blend * (pct / 100))

    if p_a >= p_d and p_a >= p_b:
        cands = {s: v for s, v in tip_scored.items() if int(s.split(':')[0]) > int(s.split(':')[1])}
    elif p_b >= p_d and p_b >= p_a:
        cands = {s: v for s, v in tip_scored.items() if int(s.split(':')[1]) > int(s.split(':')[0])}
    else:
        cands = {s: v for s, v in tip_scored.items() if s.split(':')[0] == s.split(':')[1]}
    tip = max(cands, key=cands.get) if cands else max(tip_scored, key=tip_scored.get)

    return tendency, p_a, p_d, p_b, tip


def evaluate_wm2026(verbose: bool = False, **kwargs) -> tuple[int, int]:
    """Evaluate on WM 2026 completed matches (OOS test)."""
    with open('data/fixtures.json') as f:
        fixtures = json.load(f)

    correct, total = 0, 0
    for m in fixtures:
        if m.get('status') != 'completed' or not m.get('result'):
            continue
        ga, gb = map(int, m['result'].split(':'))
        actual = 'win' if ga > gb else ('draw' if ga == gb else 'loss')
        tendency, p_a, p_d, p_b, tip = predict(m['team_a'], m['team_b'], **kwargs)
        hit = tendency == actual
        if hit:
            correct += 1
        total += 1
        if verbose:
            ra = get_rank(m['team_a'], kwargs.get('extended_ranking', True))
            rb = get_rank(m['team_b'], kwargs.get('extended_ranking', True))
            marker = '✓' if hit else '✗'
            print(f"{marker} {m['team_a']:22}(#{ra:3}) vs {m['team_b']:22}(#{rb:3}) "
                  f"→ {m['result']:5}  pred={tendency:5} tip={tip:5} [{p_a:.0%}/{p_d:.0%}/{p_b:.0%}]")
    return correct, total


def evaluate_historical(season_from: int = 2022, **kwargs) -> tuple[int, int]:
    """Evaluate on historical WM matches (NOTE: Poisson was trained on this data)."""
    with open('data/historical_matches.json') as f:
        matches = json.load(f)
    matches = [m for m in matches if m.get('season', 0) >= season_from]

    correct, total = 0, 0
    for m in matches:
        ga, gb = m['goals_a'], m['goals_b']
        actual = 'win' if ga > gb else ('draw' if ga == gb else 'loss')
        tendency, _, _, _, _ = predict(m['team_a'], m['team_b'], **kwargs)
        if tendency == actual:
            correct += 1
        total += 1
    return correct, total


def evaluate_historical_scores(season_from: int = 2006, season_to: int = 9999, **kwargs) -> tuple[dict, int, int]:
    """Score tip accuracy on historical WM data (Poisson in-sample — inflated, but useful for parameter direction)."""
    with open('data/historical_matches.json') as f:
        matches = json.load(f)
    matches = [m for m in matches if season_from <= m.get('season', 0) <= season_to]

    counts = {'exact': 0, 'difference': 0, 'tendency': 0, 'wrong': 0}
    for m in matches:
        result = f"{m['goals_a']}:{m['goals_b']}"
        _, _, _, _, tip = predict(m['team_a'], m['team_b'], **kwargs)
        acc = classify_score(tip, result)
        counts[acc] += 1

    total = sum(counts.values())
    kpts = counts['exact'] * 4 + counts['difference'] * 3 + counts['tendency'] * 2
    return counts, total, kpts


def classify_score(tip: str, result: str) -> str:
    if tip == result:
        return 'exact'
    try:
        ta, tb = map(int, tip.split(':'))
        ra, rb = map(int, result.split(':'))
        if (ta - tb) == (ra - rb):
            return 'difference'
        if ((ta > tb) == (ra > rb)) and ((ta == tb) == (ra == rb)):
            return 'tendency'
    except (ValueError, AttributeError):
        pass
    return 'wrong'


def evaluate_wm2026_scores(verbose: bool = False, **kwargs) -> tuple[dict, int, int]:
    """Evaluate score tip quality on completed WM 2026 matches.
    Returns (counts, total, kicktipp_pts) where kicktipp_pts uses 4/3/2/0 scoring.
    """
    with open('data/fixtures.json') as f:
        fixtures = json.load(f)

    counts = {'exact': 0, 'difference': 0, 'tendency': 0, 'wrong': 0}
    for m in fixtures:
        if m.get('status') != 'completed' or not m.get('result'):
            continue
        _, _, _, _, tip = predict(m['team_a'], m['team_b'], **kwargs)
        acc = classify_score(tip, m['result'])
        counts[acc] += 1
        if verbose:
            marker = '🏆' if acc == 'exact' else ('📏' if acc == 'difference' else
                                                   ('↗' if acc == 'tendency' else '✗'))
            print(f"{marker} {m['team_a']:22} vs {m['team_b']:22} "
                  f"tip={tip:5} result={m['result']:5} [{acc}]")

    total = sum(counts.values())
    kpts = counts['exact'] * 4 + counts['difference'] * 3 + counts['tendency'] * 2
    return counts, total, kpts


def score_grid_search(include_historical: bool = True) -> dict:
    """Grid search over tip_dampening × goals_scale, optimizing Kicktipp score (4/3/2/0).
    Combines WM 2026 (weight 0.6) + historical 2006-2022 (weight 0.4, in-sample).
    """
    tip_dampening_vals = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    goals_scale_vals   = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0, 2.5]

    base_kwargs = dict(elo_factor=0.75, poisson_dampening=0.8,
                       poisson_weight=0.90, draw_boost=0.30)

    rows = []
    for td in tip_dampening_vals:
        for gs in goals_scale_vals:
            kw = {**base_kwargs, 'tip_dampening': td, 'goals_scale': gs}
            c26, t26, kpts26 = evaluate_wm2026_scores(**kw)
            if include_historical:
                ch, th, kptsh = evaluate_historical_scores(season_from=2006, **kw)
                # Normalize to % then combine (OOS 2026 weighted higher)
                score = 0.6 * (kpts26 / (t26 * 4)) + 0.4 * (kptsh / (th * 4))
            else:
                score = kpts26 / (t26 * 4)
            rows.append((score, kpts26, td, gs, c26, t26))

    rows.sort(key=lambda x: (-x[0], x[2], x[3]))

    max_pts26 = (rows[0][5] if rows else 1) * 4
    hist_label = " + Hist" if include_historical else ""
    print(f"\n{'TipDamp':>8} {'GoalSc':>7}  Exact  Diff  Tend  Wrong  2026pts  Score{hist_label}")
    print("─" * 75)
    for score, kpts26, td, gs, c26, t26 in rows[:20]:
        bar = int(score * 20)
        print(f"{td:>8.1f} {gs:>7.1f}  {c26['exact']:5d} {c26['difference']:5d} "
              f"{c26['tendency']:5d} {c26['wrong']:5d}  "
              f"{kpts26:4d}/{max_pts26}   {score:.3f}  {'█' * bar}")

    best = rows[0]
    print(f"\n→ Best: tip_dampening={best[2]}, goals_scale={best[3]}  "
          f"(2026: {best[1]}pts/{max_pts26}  combined_score={best[0]:.3f})")
    return {'tip_dampening': best[2], 'goals_scale': best[3]}


def grid_search(verbose: bool = True):
    """Grid search over key parameters on WM 2026 OOS data."""
    elo_factors      = [0.0, 0.25, 0.50, 0.75, 1.0, 1.5, 2.0]
    p_weights        = [0.80, 0.85, 0.90, 1.00]
    host_bonuses     = [0.0, 0.10]
    draw_boosts      = [0.0, 0.15, 0.30, 0.50]
    dampening_vals   = [0.0, 0.20, 0.40, 0.50, 0.60, 0.70, 0.80]

    total_combos = len(elo_factors) * len(p_weights) * len(host_bonuses) * len(draw_boosts) * len(dampening_vals)
    print(f"Testing {total_combos} combinations...")
    print("Pre-computing XGBoost outputs (batch)...", flush=True)
    _warmup_xgb_cache(dampening_vals)
    print("XGBoost cache ready.", flush=True)

    print(f"\n{'elo_fac':>8} {'p_wt':>6} {'host':>5} {'draw+':>6} {'damp':>5}  "
          f"{'2026 OOS':>10}  {'2022 IS':>10}")
    print("-" * 72)

    best_score, best_params = 0, {}
    rows = []
    for ef in elo_factors:
        for pw in p_weights:
            for hb in host_bonuses:
                for db in draw_boosts:
                    for damp in dampening_vals:
                        kwargs = dict(elo_factor=ef, poisson_weight=pw,
                                      host_bonus=hb, draw_boost=db,
                                      poisson_dampening=damp)
                        c26, t26 = evaluate_wm2026(**kwargs)
                        c22, t22 = evaluate_historical(season_from=2022, **kwargs)
                        acc26 = c26 / t26 if t26 else 0
                        acc22 = c22 / t22 if t22 else 0
                        combined = acc26 * 0.6 + acc22 * 0.4
                        rows.append((combined, acc26, acc22, c26, t26, c22, t22, kwargs))
                        if combined > best_score:
                            best_score = combined
                            best_params = kwargs

    rows.sort(key=lambda x: -x[0])
    for combined, acc26, acc22, c26, t26, c22, t22, kw in rows[:15]:
        print(f"{kw['elo_factor']:>8.2f} {kw['poisson_weight']:>6.2f} "
              f"{kw['host_bonus']:>5.2f} {kw['draw_boost']:>6.2f} {kw['poisson_dampening']:>5.2f}  "
              f"{c26}/{t26}={acc26:>4.0%}      {c22}/{t22}={acc22:>4.0%}   comb={combined:.3f}")

    return best_params, best_score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--grid', action='store_true', help='Run full tendency grid search')
    parser.add_argument('--score-grid', action='store_true', help='Run score tip grid search (2026 + historical)')
    parser.add_argument('--hist', type=int, default=0, help='Show historical tendency accuracy from season')
    parser.add_argument('--hist-scores', action='store_true', help='Show historical score accuracy per WM')
    args = parser.parse_args()

    prod_kwargs = dict(elo_factor=0.75, poisson_dampening=0.8,
                       poisson_weight=0.90, draw_boost=0.30)

    print("=== WM 2026 (OOS) — Production params ===")
    c, t = evaluate_wm2026(verbose=True, **prod_kwargs)
    print(f"\n  Correct tendency: {c}/{t} = {c/t*100:.1f}%")

    print("\n=== WM 2026 — Old baseline (no Elo, 60/40) ===")
    c_old, t_old = evaluate_wm2026(
        verbose=False, elo_factor=0.0, poisson_weight=0.60,
        host_bonus=0.0, draw_boost=0.0, poisson_dampening=0.0)
    print(f"  Correct tendency: {c_old}/{t_old} = {c_old/t_old*100:.1f}%")

    if args.hist > 0:
        print(f"\n=== Historical tendency WM {args.hist}+ ===")
        ch, th = evaluate_historical(season_from=args.hist, **prod_kwargs)
        print(f"  Correct tendency: {ch}/{th} = {ch/th*100:.1f}%")

    print("\n=== WM 2026 — Score tips (production params) ===")
    sc, st, skpts = evaluate_wm2026_scores(verbose=True, **prod_kwargs,
                                           tip_dampening=0.3, goals_scale=1.5)
    max_kpts = st * 4
    print(f"\n  Exact: {sc['exact']}  Diff: {sc['difference']}  Tend: {sc['tendency']}  Wrong: {sc['wrong']}")
    print(f"  Kicktipp-Punkte: {skpts} / {max_kpts}  ({skpts/max_kpts*100:.1f}%)")

    if args.hist_scores:
        print("\n=== Historical score tips per WM (in-sample — inflated) ===")
        tip_kw = {**prod_kwargs, 'tip_dampening': 0.3, 'goals_scale': 1.5}
        for season in [2006, 2010, 2014, 2018, 2022]:
            ch2, th2, kh2 = evaluate_historical_scores(season_from=season, season_to=season, **tip_kw)
            print(f"  WM {season}: {ch2['exact']}E {ch2['difference']}D {ch2['tendency']}T "
                  f"{ch2['wrong']}W  → {kh2}/{th2*4} pts ({kh2/(th2*4)*100:.1f}%)")
        ch_all, th_all, kh_all = evaluate_historical_scores(season_from=2006, **tip_kw)
        print(f"  All hist: {kh_all}/{th_all*4} pts ({kh_all/(th_all*4)*100:.1f}%)")

    if args.grid:
        print("\n=== Tendency Grid Search (WM 2026 OOS + 2022 IS) ===")
        best_params, best_score = grid_search(verbose=True)
        print(f"\nBest params: {best_params}")
        print(f"Best combined score: {best_score:.3f}")
        evaluate_wm2026(verbose=True, **best_params)
        c_best, t_best = evaluate_wm2026(verbose=False, **best_params)
        c22b, t22b = evaluate_historical(season_from=2022, **best_params)
        c_hist, t_hist = evaluate_historical(season_from=2006, **best_params)
        print(f"\n  WM 2026 OOS: {c_best}/{t_best} = {c_best/t_best*100:.1f}%")
        print(f"  WM 2022 IS:  {c22b}/{t22b} = {c22b/t22b*100:.1f}%")
        print(f"  WM 2006-22 IS: {c_hist}/{t_hist} = {c_hist/t_hist*100:.1f}%")

    if args.score_grid:
        print("\n=== Score Grid Search (WM 2026 OOS 60% + Hist 2006-22 IS 40%) ===")
        best_score_params = score_grid_search(include_historical=True)
        print(f"\n=== Best score params — WM 2026 verbose ===")
        evaluate_wm2026_scores(verbose=True, **prod_kwargs, **best_score_params)
        sc2, st2, kpts2 = evaluate_wm2026_scores(**prod_kwargs, **best_score_params)
        print(f"\n  → tip_dampening={best_score_params['tip_dampening']}, "
              f"goals_scale={best_score_params['goals_scale']}")
        print(f"  WM 2026 Kicktipp-Punkte: {kpts2} / {st2*4}  ({kpts2/(st2*4)*100:.1f}%)")
        ch_best, th_best, khpts_best = evaluate_historical_scores(
            season_from=2006, **prod_kwargs, **best_score_params)
        print(f"  Hist 2006-22 Kicktipp-Punkte: {khpts_best} / {th_best*4}  "
              f"({khpts_best/(th_best*4)*100:.1f}%)")


if __name__ == '__main__':
    main()
