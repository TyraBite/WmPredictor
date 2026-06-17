import json
import os
import pickle
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb


@dataclass
class PredictionResult:
    prob_a: float
    prob_draw: float
    prob_b: float
    top_results: list[tuple[str, float]] = field(default_factory=list)
    tip: str = ""


POISSON_PATH = "data/model_poisson.json"
XGB_PATH = "data/model_xgb.pkl"

# Maps fixture team names to Poisson model team names (from historical_matches.json)
POISSON_NAME_MAP = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Czechia": "Czech Republic",
}

POISSON_DAMPENING = 0.8
TIP_DAMPENING     = 0.3   # less dampened → wider lambda spread for score tip margin
ELO_FACTOR = 0.75


def _fit_poisson_params(matches: list[dict]) -> dict:
    teams = sorted({m["team_a"] for m in matches} | {m["team_b"] for m in matches})
    n = len(teams)
    idx = {t: i for i, t in enumerate(teams)}

    def nll(params):
        base = params[0]
        atk, dfn = params[1:n + 1], params[n + 1:2 * n + 1]
        ll = 0.0
        for m in matches:
            i, j = idx[m["team_a"]], idx[m["team_b"]]
            la = max(np.exp(base + atk[i] - dfn[j]), 0.01)
            lb = max(np.exp(base + atk[j] - dfn[i]), 0.01)
            ll += poisson.logpmf(m["goals_a"], la) + poisson.logpmf(m["goals_b"], lb)
        return -ll

    x0 = np.zeros(2 * n + 1)
    x0[0] = np.log(1.2)
    res = minimize(nll, x0, method="L-BFGS-B", options={"maxiter": 2000})
    out = {"base_rate": float(res.x[0])}
    for t, i in idx.items():
        out[t] = {"attack": float(res.x[1 + i]), "defense": float(res.x[n + 1 + i])}
    return out


def _poisson_matrix(lam_a: float, lam_b: float, max_goals: int = 6) -> np.ndarray:
    pa = np.array([poisson.pmf(i, max(lam_a, 0.01)) for i in range(max_goals)])
    pb = np.array([poisson.pmf(j, max(lam_b, 0.01)) for j in range(max_goals)])
    mat = np.outer(pa, pb)
    return mat / mat.sum()


def _poisson_probs(params: dict, team_a: str, team_b: str,
                   feat: dict) -> tuple[float, float, float, list, list, float, float]:
    base = params.get("base_rate", np.log(1.2))
    ta = POISSON_NAME_MAP.get(team_a, team_a)
    tb = POISSON_NAME_MAP.get(team_b, team_b)
    a_raw = params.get(ta, params.get(team_a, {"attack": feat.get("attack_a", 0), "defense": feat.get("defense_a", 0)}))
    b_raw = params.get(tb, params.get(team_b, {"attack": feat.get("attack_b", 0), "defense": feat.get("defense_b", 0)}))

    # Probability lambdas (conservative dampening → accurate win/draw/loss probs)
    d = 1.0 - POISSON_DAMPENING
    lam_a = np.exp(base + a_raw["attack"] * d - b_raw["defense"] * d)
    lam_b = np.exp(base + b_raw["attack"] * d - a_raw["defense"] * d)

    elo_a = feat.get("elo_a", 1500.0)
    elo_b = feat.get("elo_b", 1500.0)
    elo_scale = 1.0
    if ELO_FACTOR > 0 and elo_a != elo_b:
        p_elo_a = 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))
        elo_scale = (2.0 * p_elo_a) ** ELO_FACTOR
        lam_a *= elo_scale
        lam_b /= elo_scale

    # Tip lambdas (less dampened → wider margin spread for score prediction)
    d_tip = 1.0 - TIP_DAMPENING
    lam_a_tip = np.exp(base + a_raw["attack"] * d_tip - b_raw["defense"] * d_tip) * elo_scale
    lam_b_tip = np.exp(base + b_raw["attack"] * d_tip - a_raw["defense"] * d_tip) / elo_scale

    mat = _poisson_matrix(lam_a, lam_b)
    n = mat.shape[0]
    p_win = float(np.tril(mat, -1).sum())
    p_draw = float(np.diag(mat).sum())
    p_loss = float(np.triu(mat, 1).sum())

    results = [(f"{i}:{j}", float(mat[i, j])) for i in range(n) for j in range(n)]
    results.sort(key=lambda x: -x[1])
    return p_win, p_draw, p_loss, results[:5], results, lam_a_tip, lam_b_tip


def _feat_to_array(feat: dict) -> np.ndarray:
    return np.array([[
        feat.get("klement_diff", 0),
        feat.get("climate_sim_a", 0.5),
        feat.get("climate_sim_b", 0.5),
        feat.get("elo_a", 1500) / 2000,
        feat.get("elo_b", 1500) / 2000,
        feat.get("attack_a", 0),
        feat.get("defense_a", 0),
        feat.get("attack_b", 0),
        feat.get("defense_b", 0),
        feat.get("live_adj_a", 0.5),
        feat.get("live_adj_b", 0.5),
        feat.get("h2h_score", 0.5),
        feat.get("odds_prob_a", 0.4),
        feat.get("odds_prob_draw", 0.25),
        feat.get("odds_prob_b", 0.35),
    ]])


class WMPredictor:
    def __init__(self):
        self._poisson_params: dict = {}
        self._xgb: CalibratedClassifierCV | None = None

    def train(self, matches: list[dict]) -> None:
        self._poisson_params = _fit_poisson_params(matches)
        X, y = [], []
        for m in matches:
            feat = {
                "elo_a": 1500, "elo_b": 1500, "klement_diff": 0,
                "climate_sim_a": 0.5, "climate_sim_b": 0.5,
                "attack_a": self._poisson_params.get(m["team_a"], {}).get("attack", 0),
                "defense_a": self._poisson_params.get(m["team_a"], {}).get("defense", 0),
                "attack_b": self._poisson_params.get(m["team_b"], {}).get("attack", 0),
                "defense_b": self._poisson_params.get(m["team_b"], {}).get("defense", 0),
                "live_adj_a": 0.5, "live_adj_b": 0.5, "h2h_score": 0.5,
                "odds_prob_a": 0.4, "odds_prob_draw": 0.25, "odds_prob_b": 0.35,
            }
            X.append(_feat_to_array(feat)[0])
            ga, gb = m["goals_a"], m["goals_b"]
            y.append(0 if ga > gb else (1 if ga == gb else 2))
        X_arr = np.array(X)
        y_arr = np.array(y)
        base = xgb.XGBClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            objective="multi:softprob", num_class=3,
            random_state=42, eval_metric="mlogloss",
        )
        _, counts = np.unique(y_arr, return_counts=True)
        cv = min(3, int(counts.min()))
        self._xgb = CalibratedClassifierCV(base, cv=cv, method="isotonic")
        self._xgb.fit(X_arr, y_arr)

    def predict(self, feat: dict, team_a: str = "A", team_b: str = "B") -> PredictionResult:
        pw, pd, pl, top5, all_results, lam_a_tip, lam_b_tip = _poisson_probs(
            self._poisson_params, team_a, team_b, feat)
        X = _feat_to_array(feat)
        xgb_probs = self._xgb.predict_proba(X)[0]
        p_a = 0.90 * pw + 0.10 * xgb_probs[0]
        p_d = 0.90 * pd + 0.10 * xgb_probs[1]
        p_b = 0.90 * pl + 0.10 * xgb_probs[2]
        # WM 2026 has anomalously high draw rate (44% vs historical 22%); apply moderate boost
        p_d *= 1.15
        raw_adj = feat.get("live_adj_a", 0.5) / max(feat.get("live_adj_b", 0.5), 0.01)
        adj = max(0.6, min(1.67, raw_adj))
        p_a *= adj
        p_b /= adj
        total = p_a + p_d + p_b
        if total > 0:
            p_a, p_d, p_b = p_a / total, p_d / total, p_b / total
        # Tip: expected goal difference from tip-lambdas (TIP_DAMPENING=0.3, less conservative)
        # Allows 2:0, 3:1 etc. for clear favorites instead of always 1:0
        raw_diff = lam_a_tip - lam_b_tip
        if p_a >= p_d and p_a >= p_b:
            exp_diff = max(1, round(raw_diff))
        elif p_b >= p_d and p_b >= p_a:
            exp_diff = min(-1, round(raw_diff))
        else:
            exp_diff = 0
        candidates = [(s, p) for s, p in all_results
                      if int(s.split(":")[0]) - int(s.split(":")[1]) == exp_diff]
        tip = candidates[0][0] if candidates else all_results[0][0]
        return PredictionResult(
            prob_a=round(p_a, 4), prob_draw=round(p_d, 4), prob_b=round(p_b, 4),
            top_results=top5, tip=tip,
        )

    def save(self, poisson_path: str = POISSON_PATH, xgb_path: str = XGB_PATH) -> None:
        os.makedirs("data", exist_ok=True)
        with open(poisson_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(self._poisson_params, indent=2))
        with open(xgb_path, "wb") as f:
            pickle.dump(self._xgb, f)

    def load(self, poisson_path: str = POISSON_PATH, xgb_path: str = XGB_PATH) -> None:
        with open(poisson_path, encoding="utf-8") as f:
            self._poisson_params = json.loads(f.read())
        with open(xgb_path, "rb") as f:
            self._xgb = pickle.load(f)
