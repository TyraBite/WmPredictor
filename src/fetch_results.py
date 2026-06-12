#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, "src")
from dotenv import load_dotenv
load_dotenv()
from data_fetcher import fetch
from fixtures import FixtureStore
from form_tracker import update_all

FD_URL = "https://api.football-data.org/v4/competitions/WC/matches"


def fetch_results(fixtures_path: str = "data/fixtures.json") -> None:
    key = os.environ.get("FOOTBALL_DATA_KEY")
    if not key:
        print("⚠️  FOOTBALL_DATA_KEY nicht gesetzt — überspringe Live-Update.")
        return

    data = fetch(FD_URL, params={"status": "FINISHED"},
                 headers={"X-Auth-Token": key}, ttl_hours=1)

    store = FixtureStore(fixtures_path)
    store.load()
    updated = 0
    for match in data.get("matches", []):
        score = match.get("score", {}).get("fullTime", {})
        ga, gb = score.get("home"), score.get("away")
        if ga is None or gb is None:
            continue
        api_id = match["id"]
        fixture = next((m for m in store._matches
                        if m.get("api_id") == api_id), None)
        if fixture and fixture["status"] == "pending":
            store.set_result(fixture["match_id"], f"{int(ga)}:{int(gb)}")
            updated += 1

    update_all(store)
    print(f"✅ {updated} Ergebnisse aktualisiert.")


if __name__ == "__main__":
    fetch_results()
