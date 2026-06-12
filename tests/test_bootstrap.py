import json
import os
import sys
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, "src")
import bootstrap_fixtures as bf


MOCK_API = {"matches": [
    {"id": 1, "utcDate": "2026-06-11T18:00:00Z",
     "stage": "GROUP_STAGE", "group": "GROUP_A", "venue": "SoFi Stadium",
     "homeTeam": {"name": "Mexico"}, "awayTeam": {"name": "Poland"},
     "score": {"fullTime": {"home": None, "away": None}}},
    {"id": 2, "utcDate": "2026-06-12T21:00:00Z",
     "stage": "GROUP_STAGE", "group": "GROUP_B", "venue": "AT&T Stadium",
     "homeTeam": {"name": "Germany"}, "awayTeam": {"name": "Japan"},
     "score": {"fullTime": {"home": None, "away": None}}},
]}


def test_map_api_response_schema():
    result = bf.map_api_response(MOCK_API)
    assert len(result) == 2
    required = {"match_id", "group", "phase", "team_a", "team_b", "flag_a", "flag_b",
                "date", "venue", "status", "result", "api_id"}
    for m in result:
        assert required.issubset(m.keys())
        assert m["status"] == "pending"
        assert m["result"] is None
        assert m["phase"] == "group"


def test_map_api_response_api_id():
    result = bf.map_api_response(MOCK_API)
    assert result[0]["api_id"] == 1
    assert result[1]["api_id"] == 2


def test_map_api_response_date_format():
    result = bf.map_api_response(MOCK_API)
    assert result[0]["date"] == "2026-06-11"


def test_map_api_response_skips_non_group():
    data = {"matches": [
        {"id": 99, "utcDate": "2026-07-01T18:00:00Z",
         "stage": "ROUND_OF_16", "group": None, "venue": "",
         "homeTeam": {"name": "Germany"}, "awayTeam": {"name": "France"},
         "score": {"fullTime": {"home": None, "away": None}}},
    ]}
    assert bf.map_api_response(data) == []


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


def test_main_no_key_exits(capsys, tmp_path):
    with patch.dict(os.environ, {}, clear=True):
        with patch("bootstrap_fixtures.os.environ.get", return_value=None):
            with pytest.raises(SystemExit) as e:
                bf.main(output_path=str(tmp_path / "f.json"))
            assert e.value.code == 1
    assert "FOOTBALL_DATA_KEY" in capsys.readouterr().out


def test_main_writes_fixtures_json(tmp_path):
    out = str(tmp_path / "fixtures.json")
    resp = MagicMock()
    resp.json.return_value = MOCK_API
    resp.raise_for_status.return_value = None
    with patch.dict(os.environ, {"FOOTBALL_DATA_KEY": "test"}):
        with patch("bootstrap_fixtures.requests.get", return_value=resp):
            bf.main(output_path=out)
    with open(out, encoding="utf-8") as f:
        data = json.loads(f.read())
    phases = {m["phase"] for m in data}
    assert "group" in phases
    assert "round_of_32" in phases
    assert "final" in phases
