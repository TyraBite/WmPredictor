import json
import pytest


@pytest.fixture
def tmp_fixtures(tmp_path):
    data = [
        {"match_id": "A1", "group": "A", "phase": "group",
         "team_a": "Germany", "team_b": "Japan",
         "flag_a": "🇩🇪", "flag_b": "🇯🇵",
         "date": "2026-06-15", "venue": "Dallas",
         "status": "pending", "result": None},
        {"match_id": "A2", "group": "A", "phase": "group",
         "team_a": "France", "team_b": "Spain",
         "flag_a": "🇫🇷", "flag_b": "🇪🇸",
         "date": "2026-06-16", "venue": "New York/NJ",
         "status": "completed", "result": "2:1"},
        {"match_id": "R32_1", "group": None, "phase": "round_of_32",
         "team_a": None, "team_b": None,
         "slot_a": "1A", "slot_b": "2B",
         "date": "2026-06-27", "venue": "Miami",
         "status": "pending", "result": None,
         "flag_a": None, "flag_b": None},
    ]
    p = tmp_path / "fixtures.json"
    p.write_text(json.dumps(data))
    return str(p)
