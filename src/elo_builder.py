#!/usr/bin/env python3
"""
Compute international Elo ratings for all WM 2026 teams from full
historical results (martj42/international_results, ~49k matches).

Updates data/elo_ratings.json with current Elo for all active nations.

Usage:
  python src/elo_builder.py            # compute + save
  python src/elo_builder.py --check    # show current Elo for WM 2026 teams
"""
import sys, json, csv, io, os, argparse
from datetime import date

sys.path.insert(0, 'src')

RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
ELO_PATH = "data/elo_ratings.json"
FIXTURES_PATH = "data/fixtures.json"

# K-factors by tournament type (higher = more weight on recent performance)
K_MAP = {
    "FIFA World Cup": 60,
    "UEFA Euro": 50, "European Championship": 50,
    "Copa America": 50, "African Cup of Nations": 50,
    "AFC Asian Cup": 50, "Gold Cup": 50, "CONCACAF Gold Cup": 50,
    "OFC Nations Cup": 45,
    "FIFA Confederations Cup": 50,
    "UEFA Nations League": 40,
    "AFC Asian Cup qualification": 35,
    "African Cup of Nations qualification": 35,
    "FIFA World Cup qualification": 40,
    "UEFA Euro qualification": 35,
    "Copa America qualification": 35,
}

DEFAULT_K_QUAL = 30   # any qualification
DEFAULT_K_FRIENDLY = 20
DEFAULT_K_OFFICIAL = 35  # official but unlisted

HOME_ADV = 100  # Elo points advantage for home team (non-neutral venue)
INIT_ELO = 1500.0


def _k_factor(tournament: str) -> float:
    if tournament in K_MAP:
        return K_MAP[tournament]
    t = tournament.lower()
    if "world cup" in t:
        return 55
    if "qualification" in t or "qualifier" in t:
        return DEFAULT_K_QUAL
    if "friendly" in t or "international" in t:
        return DEFAULT_K_FRIENDLY
    if "nations league" in t or "cup" in t or "championship" in t:
        return DEFAULT_K_OFFICIAL
    return DEFAULT_K_FRIENDLY


def _expected(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def compute_elo(csv_text: str, cutoff_date: str = None) -> dict[str, float]:
    """Compute Elo for all teams from CSV text. Optional cutoff_date='YYYY-MM-DD'."""
    elo: dict[str, float] = {}
    reader = csv.DictReader(io.StringIO(csv_text))
    cutoff = date.fromisoformat(cutoff_date) if cutoff_date else None

    for row in reader:
        d_str = row.get("date", "")
        h_score = row.get("home_score", "").strip()
        a_score = row.get("away_score", "").strip()
        if not h_score or not a_score or h_score == "NA" or a_score == "NA":
            continue
        try:
            hs, as_ = int(h_score), int(a_score)
        except ValueError:
            continue
        if cutoff and date.fromisoformat(d_str) > cutoff:
            continue

        home = row["home_team"]
        away = row["away_team"]
        neutral = row.get("neutral", "FALSE").strip().upper() == "TRUE"
        tournament = row.get("tournament", "Friendly")

        elo_h = elo.setdefault(home, INIT_ELO)
        elo_a = elo.setdefault(away, INIT_ELO)

        # Home advantage for non-neutral venues
        adj_h = elo_h + (0 if neutral else HOME_ADV)
        adj_a = elo_a

        exp_h = _expected(adj_h, adj_a)
        result_h = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)

        k = _k_factor(tournament)
        delta = k * (result_h - exp_h)
        elo[home] = max(800.0, elo_h + delta)
        elo[away] = max(800.0, elo_a - delta)

    return elo


def update_with_wm2026(elo: dict[str, float]) -> dict[str, float]:
    """Apply WM 2026 completed matches from fixtures.json to update Elo."""
    if not os.path.exists(FIXTURES_PATH):
        return elo
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        fixtures = json.load(f)
    k = K_MAP["FIFA World Cup"]
    for m in fixtures:
        if m.get("status") != "completed" or not m.get("result"):
            continue
        home, away = m["team_a"], m["team_b"]
        try:
            hs, as_ = map(int, m["result"].split(":"))
        except ValueError:
            continue
        elo_h = elo.get(home, INIT_ELO)
        elo_a = elo.get(away, INIT_ELO)
        exp_h = _expected(elo_h, elo_a)  # WM is neutral venue
        result_h = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
        delta = k * (result_h - exp_h)
        elo[home] = max(800.0, elo_h + delta)
        elo[away] = max(800.0, elo_a - delta)
    return elo


WM2026_TEAMS = [
    "Argentina", "France", "England", "Brazil", "Belgium", "Portugal",
    "Netherlands", "Spain", "Croatia", "Italy", "United States", "Mexico",
    "Germany", "Morocco", "Japan", "Colombia", "Senegal", "Denmark",
    "Uruguay", "Switzerland", "South Korea", "Ecuador", "Austria",
    "Hungary", "Turkey", "Serbia", "Ukraine", "Australia", "Iran",
    "Poland", "Saudi Arabia", "Canada", "Czech Republic", "Ivory Coast",
    "Qatar", "Nigeria", "Romania", "Slovakia", "Egypt", "Jordan",
    "Tunisia", "Norway", "Scotland", "Paraguay", "Venezuela", "Cameroon",
    "DR Congo", "New Zealand", "Sweden", "South Africa", "Cape Verde",
    "Haiti", "Bosnia and Herzegovina", "Albania", "Georgia", "Uzbekistan",
    "Iraq", "Curaçao", "Algeria", "Ghana", "Panama", "Bolivia", "Honduras",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--no-wm2026", action="store_true", help="Don't apply WM 2026 results")
    args = parser.parse_args()

    print("Fetching international results CSV...", flush=True)
    import urllib.request
    with urllib.request.urlopen(RESULTS_URL, timeout=60) as r:
        csv_text = r.read().decode("utf-8")
    print(f"Downloaded {len(csv_text):,} bytes, computing Elo...", flush=True)

    elo = compute_elo(csv_text)
    print(f"Computed Elo for {len(elo)} teams.")

    if not args.no_wm2026:
        elo = update_with_wm2026(elo)
        print("Applied WM 2026 completed results.")

    if args.check:
        print(f"\n{'Team':<30} {'Elo':>6}  {'Change vs current':>20}")
        print("-" * 60)
        with open(ELO_PATH) as f:
            old = json.load(f)
        for team in sorted(WM2026_TEAMS, key=lambda t: -elo.get(t, 0)):
            e = elo.get(team, INIT_ELO)
            old_e = old.get(team, INIT_ELO)
            delta = e - old_e
            print(f"{team:<30} {e:>6.0f}  {old_e:>6.0f} → {delta:>+5.0f}")
        return

    # Save only teams we need (all from ELO_PATH + WM2026 teams)
    save = {t: round(elo[t], 1) for t in elo}
    with open(ELO_PATH, "w", encoding="utf-8") as f:
        json.dump(save, f, indent=2, ensure_ascii=False, sort_keys=True)
    print(f"Saved {len(save)} teams to {ELO_PATH}")


if __name__ == "__main__":
    main()
