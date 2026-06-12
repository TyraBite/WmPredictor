import json
import os
import sys
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, "src")
import bootstrap_fixtures as bf


MOCK_API = {"response": [
    {"fixture": {"id": 1, "date": "2026-06-11T18:00:00+00:00",
                 "venue": {"city": "Los Angeles", "name": "SoFi Stadium"},
                 "status": {"short": "NS"}},
     "league": {"round": "Group A"},
     "teams": {"home": {"name": "Mexico"}, "away": {"name": "Poland"}}},
    {"fixture": {"id": 2, "date": "2026-06-12T21:00:00+00:00",
                 "venue": {"city": "Dallas", "name": "AT&T Stadium"},
                 "status": {"short": "NS"}},
     "league": {"round": "Group B"},
     "teams": {"home": {"name": "Germany"}, "away": {"name": "Japan"}}},
]}


def test_map_api_response_schema():
    result = bf.map_api_response(MOCK_API)
    assert len(result) == 2
    required = {"match_id","group","phase","team_a","team_b","flag_a","flag_b",
                "date","venue","status","result"}
    for m in result:
        assert required.issubset(m.keys())
        assert m["status"] == "pending"
        assert m["result"] is None
        assert m["phase"] == "group"


def test_map_api_response_venue_normalization():
    result = bf.map_api_response(MOCK_API)
    assert result[0]["venue"] == "Los Angeles"
    assert result[1]["venue"] == "Dallas"


def test_map_api_response_date_format():
    result = bf.map_api_response(MOCK_API)
    assert result[0]["date"] == "2026-06-11"


def test_generate_ko_bracket_counts():
    slots = bf.generate_ko_bracket()
    phases = {s["phase"] for s in slots}
    assert "round_of_32" in phases
    assert "round_of_16" in phases
    assert "quarter_final" in phases
    assert "semi_final" in phases
    assert "final" in phases
    assert len([s for s in slots if s["phase"] == "round_of_32"]) == 16
    assert len([s for s in slots if s["phase"] == "final"]) == 1


def test_generate_ko_bracket_null_teams():
    for s in bf.generate_ko_bracket():
        assert s["team_a"] is None
        assert s["team_b"] is None


def test_all_16_venues_in_city_to_venue():
    expected = {"New York/NJ","Los Angeles","Dallas","San Francisco","Seattle",
                "Miami","Houston","Atlanta","Philadelphia","Kansas City","Boston",
                "Toronto","Vancouver","Mexico City","Guadalajara","Monterrey"}
    assert expected == set(bf.CITY_TO_VENUE.values())


def test_main_no_key_exits(capsys, tmp_path):
    with patch.dict(os.environ, {}, clear=True):
        with patch("bootstrap_fixtures.os.environ.get", return_value=None):
            with pytest.raises(SystemExit) as e:
                bf.main(output_path=str(tmp_path / "f.json"))
            assert e.value.code == 1
    assert "API_FOOTBALL_KEY" in capsys.readouterr().out


def test_main_writes_fixtures_json(tmp_path):
    out = str(tmp_path / "fixtures.json")
    resp = MagicMock()
    resp.json.return_value = MOCK_API
    resp.raise_for_status.return_value = None
    with patch.dict(os.environ, {"API_FOOTBALL_KEY": "test"}):
        with patch("bootstrap_fixtures.requests.get", return_value=resp):
            bf.main(output_path=out)
    data = json.loads(open(out).read())
    phases = {m["phase"] for m in data}
    assert "group" in phases
    assert "round_of_32" in phases
    assert "final" in phases
