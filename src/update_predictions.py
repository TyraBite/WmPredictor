#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone
sys.path.insert(0, "src")
from dotenv import load_dotenv
load_dotenv()
from fixtures import FixtureStore
from features import build as build_features
from model import WMPredictor, PredictionResult
from form_tracker import update_all


def build_predictions_json(
        fixtures_path: str = "data/fixtures.json",
        output_path: str = "docs/predictions.json",
        form_path: str = "data/form_cache.json",
        injury_path: str = "data/injuries.json",
        klement_path: str = "data/klement_scores.json") -> None:

    store = FixtureStore(fixtures_path)
    store.load()
    update_all(store, form_path=form_path, injury_path=injury_path)

    predictor = WMPredictor()
    try:
        predictor.load()
    except FileNotFoundError:
        print("⚠️  Kein trainiertes Modell — predictions.json wird ohne ML-Scores erstellt.")

    form_cache = {}
    if os.path.exists(form_path):
        with open(form_path, encoding="utf-8") as f:
            form_cache = json.loads(f.read())
    injuries = {}
    if os.path.exists(injury_path):
        with open(injury_path, encoding="utf-8") as f:
            injuries = json.loads(f.read())
    klement = {}
    if os.path.exists(klement_path):
        with open(klement_path, encoding="utf-8") as f:
            klement = json.loads(f.read())

    warnings = []
    if not os.environ.get("ODDS_API_KEY"):
        warnings.append("Wettquoten nicht verfügbar (ODDS_API_KEY fehlt)")
    if not os.environ.get("API_FOOTBALL_KEY"):
        warnings.append("Live-Updates nicht verfügbar (API_FOOTBALL_KEY fehlt)")

    pending_out = []
    for m in store.pending():
        feat = build_features(m["team_a"], m["team_b"], m["venue"])
        if predictor._xgb:
            feat["attack_a"] = predictor._poisson_params.get(m["team_a"], {}).get("attack", 0)
            feat["defense_a"] = predictor._poisson_params.get(m["team_a"], {}).get("defense", 0)
            feat["attack_b"] = predictor._poisson_params.get(m["team_b"], {}).get("attack", 0)
            feat["defense_b"] = predictor._poisson_params.get(m["team_b"], {}).get("defense", 0)
            r = predictor.predict(feat, m["team_a"], m["team_b"])
        else:
            r = PredictionResult(0.4, 0.25, 0.35,
                                 [("1:1", 0.10), ("1:0", 0.09), ("0:1", 0.08)], "1:1")

        fa = form_cache.get(m["team_a"], {}).get("recent_matches", [])
        fb = form_cache.get(m["team_b"], {}).get("recent_matches", [])
        inj_a_entry = injuries.get(m["team_a"], {})
        inj_b_entry = injuries.get(m["team_b"], {})
        inj_a = ([f"{p} ❌" for p in inj_a_entry.get("injured", [])] +
                 [f"{p} 🟥" for p in inj_a_entry.get("suspended", [])])
        inj_b = ([f"{p} ❌" for p in inj_b_entry.get("injured", [])] +
                 [f"{p} 🟥" for p in inj_b_entry.get("suspended", [])])

        phase = m.get("phase", "group")
        pending_out.append({
            "match_id": m["match_id"],
            "group": m.get("group"),
            "phase": phase,
            "team_a": m["team_a"],
            "flag_a": m.get("flag_a", ""),
            "team_b": m["team_b"],
            "flag_b": m.get("flag_b", ""),
            "date": m["date"],
            "venue": m["venue"],
            "prob_a": round(r.prob_a * 100, 1),
            "prob_draw": round(r.prob_draw * 100, 1),
            "prob_b": round(r.prob_b * 100, 1),
            "tip": r.tip,
            "top_results": [[s, round(p * 100, 1)] for s, p in r.top_results],
            "klement_a": round(klement.get(m["team_a"], {}).get("klement_score", 0), 2),
            "klement_b": round(klement.get(m["team_b"], {}).get("klement_score", 0), 2),
            "form_a": fa,
            "form_b": fb,
            "injuries_a": inj_a,
            "injuries_b": inj_b,
        })

    completed = store.completed()
    if completed:
        phases_order = ["group", "round_of_32", "round_of_16",
                        "quarter_final", "semi_final", "final"]
        latest_phase = max(
            (m.get("phase", "group") for m in completed),
            key=lambda p: phases_order.index(p) if p in phases_order else 0,
        )
        tournament_phases = {
            "group": "Gruppenphase", "round_of_32": "Achtelfinale",
            "round_of_16": "Sechzehntelfinale", "quarter_final": "Viertelfinale",
            "semi_final": "Halbfinale", "final": "Finale",
        }
        tournament_phase = tournament_phases.get(latest_phase, "Gruppenphase")
    else:
        tournament_phase = "Gruppenphase"

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "tournament_phase": tournament_phase,
        "warnings": warnings,
        "pending_matches": pending_out,
    }
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"✅ {len(pending_out)} ausstehende Spiele → {output_path}")


if __name__ == "__main__":
    build_predictions_json()
