import json
import os
import sys
from data_fetcher import fetch
from fixtures import FixtureStore

KLEMENT_PATH = "data/klement_scores.json"
ELO_PATH = "data/elo_ratings.json"
HISTORICAL_PATH = "data/historical_matches.json"
STORE_PATH = "data/fixtures.json"

WB_URL = "https://api.worldbank.org/v2/country/{iso}/indicator/{ind}?format=json&mrv=1"
METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
HISTORICAL_MATCHES_PATH = "data/historical_matches.json"

TEAM_ISO: dict[str, str] = {
    "Argentina": "AR", "Brazil": "BR", "Colombia": "CO", "Uruguay": "UY",
    "Ecuador": "EC", "Venezuela": "VE", "Paraguay": "PY", "Chile": "CL",
    "Peru": "PE", "Bolivia": "BO",
    "Germany": "DE", "France": "FR", "Spain": "ES", "Portugal": "PT",
    "England": "GB", "Netherlands": "NL", "Belgium": "BE", "Croatia": "HR",
    "Denmark": "DK", "Switzerland": "CH", "Serbia": "RS", "Poland": "PL",
    "Ukraine": "UA", "Austria": "AT", "Turkey": "TR", "Slovakia": "SK",
    "Hungary": "HU", "Czech Republic": "CZ", "Scotland": "GB", "Romania": "RO",
    "Slovenia": "SI", "Albania": "AL", "Georgia": "GE",
    "USA": "US", "Mexico": "MX", "Canada": "CA", "Costa Rica": "CR",
    "Panama": "PA", "Honduras": "HN", "Jamaica": "JM", "Cuba": "CU",
    "Morocco": "MA", "Senegal": "SN", "Nigeria": "NG", "Egypt": "EG",
    "DR Congo": "CD", "South Africa": "ZA", "Ivory Coast": "CI", "Tunisia": "TN",
    "Cameroon": "CM", "Ghana": "GH", "Mali": "ML", "Algeria": "DZ",
    "Japan": "JP", "South Korea": "KR", "Korea Republic": "KR",
    "Saudi Arabia": "SA", "Iran": "IR", "Australia": "AU", "Iraq": "IQ",
    "Jordan": "JO", "Qatar": "QA", "Uzbekistan": "UZ", "New Zealand": "NZ",
}

TEAM_HOME_COORDS: dict[str, tuple[float, float]] = {
    "Argentina": (-34.60, -58.38), "Brazil": (-23.55, -46.63),
    "Colombia": (4.60, -74.08), "Uruguay": (-34.90, -56.19),
    "Ecuador": (-0.23, -78.52), "Venezuela": (10.49, -66.88),
    "Paraguay": (-25.29, -57.64), "Chile": (-33.46, -70.65),
    "Peru": (-12.05, -77.04), "Bolivia": (-16.50, -68.15),
    "Germany": (52.52, 13.41), "France": (48.85, 2.35),
    "Spain": (40.42, -3.70), "Portugal": (38.72, -9.14),
    "England": (51.51, -0.13), "Netherlands": (52.37, 4.90),
    "Belgium": (50.85, 4.35), "Croatia": (45.81, 15.98),
    "Denmark": (55.68, 12.57), "Switzerland": (46.95, 7.45),
    "Serbia": (44.80, 20.46), "Poland": (52.23, 21.01),
    "Ukraine": (50.45, 30.52), "Austria": (48.21, 16.37),
    "Turkey": (41.01, 28.95), "Slovakia": (48.15, 17.11),
    "Hungary": (47.50, 19.04), "Czech Republic": (50.09, 14.42),
    "Scotland": (55.86, -4.25), "Romania": (44.44, 26.10),
    "USA": (40.71, -74.01), "Mexico": (19.43, -99.13),
    "Canada": (43.65, -79.38), "Costa Rica": (9.93, -84.08),
    "Panama": (8.99, -79.52), "Honduras": (14.07, -87.21),
    "Morocco": (33.59, -7.62), "Senegal": (14.72, -17.47),
    "Nigeria": (6.45, 3.40), "Egypt": (30.04, 31.24),
    "DR Congo": (-4.32, 15.32), "South Africa": (-26.20, 28.04),
    "Ivory Coast": (5.35, -4.00), "Tunisia": (36.82, 10.18),
    "Cameroon": (3.87, 11.52),
    "Japan": (35.69, 139.69), "South Korea": (37.57, 126.98),
    "Korea Republic": (37.57, 126.98), "Saudi Arabia": (24.69, 46.72),
    "Iran": (35.69, 51.39), "Australia": (-37.81, 144.96),
    "Iraq": (33.34, 44.40), "Jordan": (31.96, 35.95),
    "Qatar": (25.29, 51.53), "New Zealand": (-36.87, 174.77),
}

VENUE_COORDS: dict[str, tuple[float, float]] = {
    "New York/NJ": (40.81, -74.07), "Los Angeles": (33.95, -118.34),
    "Dallas": (32.75, -97.09), "San Francisco": (37.40, -121.97),
    "Seattle": (47.60, -122.33), "Miami": (25.96, -80.24),
    "Houston": (29.69, -95.41), "Atlanta": (33.76, -84.40),
    "Philadelphia": (39.90, -75.17), "Kansas City": (39.05, -94.48),
    "Boston": (42.09, -71.26), "Toronto": (43.63, -79.42),
    "Vancouver": (49.28, -123.11), "Mexico City": (19.30, -99.15),
    "Guadalajara": (20.67, -103.31), "Monterrey": (25.67, -100.31),
}

FIFA_RANKING: dict[str, int] = {
    "Argentina": 1, "France": 2, "England": 3, "Brazil": 4, "Belgium": 5,
    "Portugal": 6, "Netherlands": 7, "Spain": 8, "Croatia": 9, "Italy": 10,
    "USA": 11, "Mexico": 12, "Germany": 13, "Morocco": 14, "Japan": 15,
    "Colombia": 16, "Senegal": 17, "Denmark": 18, "Uruguay": 19,
    "Switzerland": 20, "South Korea": 21, "Ecuador": 22, "Austria": 23,
    "Hungary": 24, "Turkey": 25, "Serbia": 26, "Ukraine": 27,
    "Australia": 28, "Iran": 29, "Poland": 30, "Saudi Arabia": 31,
    "Canada": 32, "Czech Republic": 33, "Ivory Coast": 34, "Qatar": 35,
    "Nigeria": 36, "Romania": 37, "Slovakia": 38, "Egypt": 39,
    "Jordan": 40, "Tunisia": 41, "Norway": 42, "Scotland": 43,
    "Paraguay": 44, "Venezuela": 45, "Cameroon": 46,
    "DR Congo": 47, "New Zealand": 48,
}


def _norm(vals: dict[str, float]) -> dict[str, float]:
    mn, mx = min(vals.values()), max(vals.values())
    if mx == mn:
        return {k: 0.5 for k in vals}
    return {k: (v - mn) / (mx - mn) for k, v in vals.items()}


def _elo_update(elo_a: float, elo_b: float, result: str, k: float = 32
                ) -> tuple[float, float]:
    exp_a = 1 / (1 + 10 ** ((elo_b - elo_a) / 400))
    score = {"win": 1.0, "draw": 0.5, "loss": 0.0}[result]
    delta = k * (score - exp_a)
    return elo_a + delta, elo_b - delta


def _avg_temp(lat: float, lon: float) -> float:
    data = fetch(METEO_URL, params={
        "latitude": lat, "longitude": lon,
        "start_date": "2019-06-01", "end_date": "2024-07-31",
        "daily": "temperature_2m_max", "timezone": "UTC",
    }, ttl_hours=24 * 365)
    temps = data.get("daily", {}).get("temperature_2m_max", [])
    valid = [t for t in temps if t is not None]
    return sum(valid) / len(valid) if valid else 20.0


def _wb_value(iso: str, indicator: str) -> float:
    url = WB_URL.format(iso=iso, ind=indicator)
    data = fetch(url, ttl_hours=24 * 365)
    try:
        return float(data[1][0]["value"] or 0)
    except Exception:
        return 0.0


def _load_historical_matches() -> list[dict]:
    if not os.path.exists(HISTORICAL_MATCHES_PATH):
        print(f"  {HISTORICAL_MATCHES_PATH} nicht gefunden — kein historisches Training.")
        return []
    with open(HISTORICAL_MATCHES_PATH, encoding="utf-8") as f:
        return json.load(f)


def compute_all() -> None:
    store = FixtureStore(STORE_PATH)
    try:
        store.load()
    except FileNotFoundError:
        pass
    teams = list(store.all_teams()) or list(TEAM_HOME_COORDS.keys())

    pop_raw, gdp_raw = {}, {}
    for team in teams:
        iso = TEAM_ISO.get(team, "US")
        pop_raw[team] = _wb_value(iso, "SP.POP.TOTL")
        gdp_raw[team] = _wb_value(iso, "NY.GDP.PCAP.CD")
    pop_norm = _norm(pop_raw)
    gdp_norm = _norm(gdp_raw)

    home_climate = {}
    for team in teams:
        coords = TEAM_HOME_COORDS.get(team, (0.0, 0.0))
        home_climate[team] = _avg_temp(*coords)

    venue_climate = {v: _avg_temp(*c) for v, c in VENUE_COORDS.items()}

    rank_raw = {t: float(FIFA_RANKING.get(t, 50)) for t in teams}
    rank_norm = _norm(rank_raw)

    klement_data = {}
    for team in teams:
        score = (0.25 * pop_norm[team] + 0.35 * gdp_norm[team]
                 + 0.25 * (1 - rank_norm[team]))
        klement_data[team] = {
            "klement_score": round(score, 4),
            "home_climate": round(home_climate.get(team, 20.0), 2),
            "venue_climates": {v: round(t, 2) for v, t in venue_climate.items()},
            "population": pop_raw[team],
            "gdp_per_capita": gdp_raw[team],
            "fifa_ranking": FIFA_RANKING.get(team, 50),
        }

    elo: dict[str, float] = {t: 1500.0 for t in teams}
    historical = _load_historical_matches()
    for m in historical:
        ta, tb = m["team_a"], m["team_b"]
        if ta not in elo:
            elo[ta] = 1500.0
        if tb not in elo:
            elo[tb] = 1500.0
        ga, gb = m["goals_a"], m["goals_b"]
        result = "win" if ga > gb else ("draw" if ga == gb else "loss")
        elo[ta], elo[tb] = _elo_update(elo[ta], elo[tb], result)

    os.makedirs("data", exist_ok=True)
    with open(KLEMENT_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(klement_data, indent=2))
    with open(ELO_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps({t: round(v, 1) for t, v in elo.items()}, indent=2))
    with open(HISTORICAL_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(historical, indent=2))
    print(f"Klement scores + Elo ratings computed for {len(teams)} teams.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    compute_all()
