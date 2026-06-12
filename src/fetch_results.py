#!/usr/bin/env python3
import json
import os
import sys
from datetime import date
sys.path.insert(0, "src")
from dotenv import load_dotenv
load_dotenv()
from data_fetcher import fetch
from fixtures import FixtureStore
from form_tracker import update_all

AF_URL = "https://v3.football.api-sports.io/fixtures"
WORLD_CUP_LEAGUE_ID = 1


def fetch_results(fixtures_path: str = "data/fixtures.json") -> None:
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        print("⚠️  API_FOOTBALL_KEY nicht gesetzt — überspringe Live-Update.")
        return

    today = date.today().isoformat()
    data = fetch(AF_URL, params={"league": WORLD_CUP_LEAGUE_ID, "season": 2026,
                                 "date": today, "status": "FT"},
                 headers={"x-apisports-key": key}, ttl_hours=1)

    store = FixtureStore(fixtures_path)
    store.load()
    updated = 0
    for item in data.get("response", []):
        goals = item.get("goals", {})
        ga, gb = goals.get("home"), goals.get("away")
        if ga is None or gb is None:
            continue
        api_id = item["fixture"]["id"]
        match = next((m for m in store._matches
                      if m.get("api_id") == api_id), None)
        if match and match["status"] == "pending":
            store.set_result(match["match_id"], f"{int(ga)}:{int(gb)}")
            updated += 1

    update_all(store)
    print(f"✅ {updated} Ergebnisse aktualisiert.")


if __name__ == "__main__":
    fetch_results()
