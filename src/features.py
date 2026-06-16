import json
import os
from form_tracker import get_adjustment
from klement import FIFA_RANKING

KLEMENT_PATH = "data/klement_scores.json"
ELO_PATH = "data/elo_ratings.json"
HISTORICAL_PATH = "data/historical_matches.json"
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds"

ODDS_NAME_MAP = {
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "Cape Verde Islands": "Cape Verde",
    "Congo DR": "DR Congo",
    "Czechia": "Czech Republic",
    "United States": "USA",
}


def _h2h_score(team_a: str, team_b: str) -> float:
    if not os.path.exists(HISTORICAL_PATH):
        return 0.5
    with open(HISTORICAL_PATH, encoding="utf-8") as f:
        matches = json.loads(f.read())
    h2h = [m for m in matches
           if (m["team_a"] == team_a and m["team_b"] == team_b)
           or (m["team_a"] == team_b and m["team_b"] == team_a)]
    h2h = h2h[-10:]
    if not h2h:
        return 0.5
    pts, total = 0.0, 0.0
    for i, m in enumerate(h2h):
        w = (i + 1) / len(h2h)
        if m["team_a"] == team_a:
            pts += w * (1.0 if m["goals_a"] > m["goals_b"] else
                        (0.5 if m["goals_a"] == m["goals_b"] else 0.0))
        else:
            pts += w * (1.0 if m["goals_b"] > m["goals_a"] else
                        (0.5 if m["goals_a"] == m["goals_b"] else 0.0))
        total += w
    return pts / total if total > 0 else 0.5


def _odds_probs(team_a: str, team_b: str) -> tuple[float, float, float]:
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        return 0.4, 0.25, 0.35
    try:
        from data_fetcher import fetch
        data = fetch(ODDS_API_URL, params={"apiKey": key, "regions": "eu",
                                           "markets": "h2h", "oddsFormat": "decimal"})
        odds_a = ODDS_NAME_MAP.get(team_a, team_a)
        odds_b = ODDS_NAME_MAP.get(team_b, team_b)
        for event in data:
            teams = {event.get("home_team", ""), event.get("away_team", "")}
            if odds_a in teams and odds_b in teams:
                for bm in event.get("bookmakers", [])[:1]:
                    for mkt in bm.get("markets", []):
                        if mkt["key"] == "h2h":
                            outcomes = {o["name"]: o["price"] for o in mkt["outcomes"]}
                            q = {k: 1 / v for k, v in outcomes.items() if v > 0}
                            total_q = sum(q.values())
                            return (q.get(team_a, 0) / total_q,
                                    q.get("Draw", 0) / total_q,
                                    q.get(team_b, 0) / total_q)
    except Exception:
        pass
    return 0.4, 0.25, 0.35


def fetch_score_odds(team_a: str, team_b: str) -> dict:
    """Returns {score: implied_prob_pct} from bookmaker correct_score market, or {} if unavailable."""
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        return {}
    try:
        from data_fetcher import fetch
        data = fetch(ODDS_API_URL, params={"apiKey": key, "regions": "eu",
                                           "markets": "correct_score", "oddsFormat": "decimal"},
                     ttl_hours=1)
        odds_a = ODDS_NAME_MAP.get(team_a, team_a)
        odds_b = ODDS_NAME_MAP.get(team_b, team_b)
        for event in data:
            home = event.get("home_team", "")
            away = event.get("away_team", "")
            if {odds_a, odds_b} != {home, away}:
                continue
            a_is_home = home == odds_a
            for bm in event.get("bookmakers", [])[:1]:
                for mkt in bm.get("markets", []):
                    if mkt["key"] != "correct_score":
                        continue
                    result = {}
                    for o in mkt.get("outcomes", []):
                        price = o.get("price", 0)
                        if price <= 0:
                            continue
                        # Outcome name is typically "1-0", "2-1" (home:away)
                        raw = o["name"].replace(" ", "")
                        parts = raw.split("-")
                        if len(parts) != 2:
                            continue
                        try:
                            gh, ga_val = int(parts[0]), int(parts[1])
                        except ValueError:
                            continue
                        score = f"{gh}:{ga_val}" if a_is_home else f"{ga_val}:{gh}"
                        result[score] = round(100 / price, 1)
                    return result
    except Exception:
        pass
    return {}


def build(team_a: str, team_b: str, venue: str) -> dict:
    klement = {}
    if os.path.exists(KLEMENT_PATH):
        with open(KLEMENT_PATH, encoding="utf-8") as f:
            klement = json.loads(f.read())
    elo_data = {}
    if os.path.exists(ELO_PATH):
        with open(ELO_PATH, encoding="utf-8") as f:
            elo_data = json.loads(f.read())

    ka = klement.get(team_a, {})
    kb = klement.get(team_b, {})

    climate_a = ka.get("home_climate", 20.0)
    climate_b = kb.get("home_climate", 20.0)
    venue_temp = ka.get("venue_climates", {}).get(venue, 20.0)

    odds_a, odds_draw, odds_b = _odds_probs(team_a, team_b)

    return {
        "klement_diff": ka.get("klement_score", 0.5) - kb.get("klement_score", 0.5),
        "climate_sim_a": 1 - abs(climate_a - venue_temp) / 40,
        "climate_sim_b": 1 - abs(climate_b - venue_temp) / 40,
        "elo_a": elo_data.get(team_a, 1500.0),
        "elo_b": elo_data.get(team_b, 1500.0),
        "attack_a": 0.0,
        "defense_a": 0.0,
        "attack_b": 0.0,
        "defense_b": 0.0,
        "live_adj_a": get_adjustment(team_a),
        "live_adj_b": get_adjustment(team_b),
        "h2h_score": _h2h_score(team_a, team_b),
        "odds_prob_a": odds_a,
        "odds_prob_draw": odds_draw,
        "odds_prob_b": odds_b,
        "rank_a": FIFA_RANKING.get(ODDS_NAME_MAP.get(team_a, team_a), FIFA_RANKING.get(team_a, 40)),
        "rank_b": FIFA_RANKING.get(ODDS_NAME_MAP.get(team_b, team_b), FIFA_RANKING.get(team_b, 40)),
    }
