import json
import os

FORM_PATH = "data/form_cache.json"
INJURY_PATH = "data/injuries.json"
ELO_PATH = "data/elo_ratings.json"
HISTORICAL_PATH = "data/historical_matches.json"


def _parse_result(result_str: str, team: str, match: dict) -> tuple[int, int]:
    ga, gb = map(int, result_str.split(":"))
    if match["team_a"] == team:
        return ga, gb
    return gb, ga


def _turnier_form(team: str, completed: list[dict]) -> float:
    team_matches = [m for m in completed
                    if m.get("status") == "completed" and m.get("result")
                    and (m.get("team_a") == team or m.get("team_b") == team)]
    if not team_matches:
        return 0.5

    weighted_sum = 0.0
    max_possible = 0.0
    for i, m in enumerate(team_matches):
        gf, ga = _parse_result(m["result"], team, m)
        diff = gf - ga
        pts = 3.0 if gf > ga else (1.0 if gf == ga else 0.0)
        bonus = max(-1.0, min(1.0, diff * 0.2))
        w = 2.0 if i == len(team_matches) - 1 else 1.0
        weighted_sum += (pts + bonus) * w
        max_possible += (3.0 + 1.0) * w

    return max(0.0, min(1.0, weighted_sum / max_possible)) if max_possible > 0 else 0.5


def _pre_tournament_form(team: str) -> float:
    if not os.path.exists(HISTORICAL_PATH) or not os.path.exists(ELO_PATH):
        return 0.5
    with open(HISTORICAL_PATH, encoding="utf-8") as f:
        historical = json.loads(f.read())
    with open(ELO_PATH, encoding="utf-8") as f:
        elo = json.loads(f.read())

    team_matches = [m for m in historical
                    if m.get("team_a") == team or m.get("team_b") == team]
    team_matches = team_matches[-10:]
    if not team_matches:
        return 0.5

    weighted_sum = 0.0
    weight_total = 0.0
    for m in team_matches:
        gf = m["goals_a"] if m["team_a"] == team else m["goals_b"]
        ga = m["goals_b"] if m["team_a"] == team else m["goals_a"]
        opponent = m["team_b"] if m["team_a"] == team else m["team_a"]
        pts = 1.0 if gf > ga else (1 / 3 if gf == ga else 0.0)
        opp_elo = elo.get(opponent, 1500.0)
        w = opp_elo / 2000.0
        weighted_sum += pts * w
        weight_total += w

    return weighted_sum / weight_total if weight_total > 0 else 0.5


def get_adjustment(team: str,
                   form_path: str = FORM_PATH,
                   injury_path: str = INJURY_PATH) -> float:
    form_cache = {}
    if os.path.exists(form_path):
        with open(form_path, encoding="utf-8") as f:
            form_cache = json.loads(f.read())
    injuries = {}
    if os.path.exists(injury_path):
        with open(injury_path, encoding="utf-8") as f:
            injuries = json.loads(f.read())

    entry = form_cache.get(team, {})
    tf = entry.get("turnier_form", 0.5)
    pf = entry.get("pre_tournament_form", 0.5)
    impact = injuries.get(team, {}).get("impact_score", 0.0)

    return 0.5 * tf + 0.2 * pf + 0.3 * (1.0 + impact)


def update_all(store, form_path: str = FORM_PATH, injury_path: str = INJURY_PATH) -> None:
    completed = store.completed()
    teams = store.all_teams()
    cache = {}
    for team in teams:
        tf = _turnier_form(team, completed)
        pf = _pre_tournament_form(team)
        recent = []
        team_matches = [m for m in completed
                        if m.get("team_a") == team or m.get("team_b") == team]
        for m in team_matches[-3:]:
            gf, ga = _parse_result(m["result"], team, m)
            recent.append("W" if gf > ga else ("D" if gf == ga else "L"))
        cache[team] = {
            "turnier_form": round(tf, 4),
            "pre_tournament_form": round(pf, 4),
            "recent_matches": recent,
        }

    os.makedirs(os.path.dirname(os.path.abspath(form_path)), exist_ok=True)
    with open(form_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(cache, indent=2))
