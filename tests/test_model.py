import json
import sys
import math
import pytest
sys.path.insert(0, "src")
from model import WMPredictor, PredictionResult, _fit_poisson_params, _poisson_matrix


MATCHES = [
    {"team_a": "Germany", "team_b": "Brazil", "goals_a": 1, "goals_b": 0},
    {"team_a": "Brazil", "team_b": "Argentina", "goals_a": 2, "goals_b": 1},
    {"team_a": "Germany", "team_b": "Argentina", "goals_a": 0, "goals_b": 1},
    {"team_a": "Germany", "team_b": "Brazil", "goals_a": 2, "goals_b": 2},
    {"team_a": "Brazil", "team_b": "Germany", "goals_a": 1, "goals_b": 2},
    {"team_a": "Argentina", "team_b": "Germany", "goals_a": 0, "goals_b": 0},
]


def test_fit_poisson_params_returns_expected_keys():
    params = _fit_poisson_params(MATCHES)
    assert "base_rate" in params
    assert "Germany" in params
    assert "attack" in params["Germany"]
    assert "defense" in params["Germany"]


def test_poisson_matrix_sums_to_one():
    mat = _poisson_matrix(1.2, 1.0)
    assert abs(mat.sum() - 1.0) < 0.01


def test_prediction_result_probs_sum_to_one():
    p = WMPredictor()
    p.train(MATCHES)
    feat = {
        "klement_diff": 0.1, "climate_sim_a": 0.8, "climate_sim_b": 0.7,
        "elo_a": 1600.0, "elo_b": 1500.0,
        "attack_a": 0.1, "defense_a": -0.05, "attack_b": 0.0, "defense_b": 0.0,
        "live_adj_a": 0.6, "live_adj_b": 0.5,
        "h2h_score": 0.6, "odds_prob_a": 0.4, "odds_prob_draw": 0.25, "odds_prob_b": 0.35,
    }
    result = p.predict(feat)
    total = result.prob_a + result.prob_draw + result.prob_b
    assert abs(total - 1.0) < 0.01


def test_prediction_result_type():
    p = WMPredictor()
    p.train(MATCHES)
    feat = {
        "klement_diff": 0.0, "climate_sim_a": 0.5, "climate_sim_b": 0.5,
        "elo_a": 1500.0, "elo_b": 1500.0,
        "attack_a": 0.0, "defense_a": 0.0, "attack_b": 0.0, "defense_b": 0.0,
        "live_adj_a": 0.5, "live_adj_b": 0.5,
        "h2h_score": 0.5, "odds_prob_a": 0.4, "odds_prob_draw": 0.25, "odds_prob_b": 0.35,
    }
    r = p.predict(feat)
    assert isinstance(r, PredictionResult)
    assert len(r.top_results) == 5
    assert ":" in r.tip


def test_save_load_roundtrip(tmp_path):
    p = WMPredictor()
    p.train(MATCHES)
    p.save(poisson_path=str(tmp_path / "poisson.json"), xgb_path=str(tmp_path / "xgb.pkl"))
    p2 = WMPredictor()
    p2.load(poisson_path=str(tmp_path / "poisson.json"), xgb_path=str(tmp_path / "xgb.pkl"))
    feat = {
        "klement_diff": 0.0, "climate_sim_a": 0.5, "climate_sim_b": 0.5,
        "elo_a": 1500.0, "elo_b": 1500.0, "attack_a": 0.0, "defense_a": 0.0,
        "attack_b": 0.0, "defense_b": 0.0, "live_adj_a": 0.5, "live_adj_b": 0.5,
        "h2h_score": 0.5, "odds_prob_a": 0.4, "odds_prob_draw": 0.25, "odds_prob_b": 0.35,
    }
    r = p2.predict(feat)
    assert abs(r.prob_a + r.prob_draw + r.prob_b - 1.0) < 0.01
