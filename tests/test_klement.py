import json, sys
from unittest.mock import patch, MagicMock
import pytest
sys.path.insert(0, "src")
import klement


def wb_response(value):
    return [{"page": 1}, [{"value": value, "date": "2022"}]]


def meteo_response(temps):
    return {"daily": {"temperature_2m_max": temps}}


def mock_fetch(url, **kwargs):
    if "worldbank" in url and "SP.POP.TOTL" in url:
        return wb_response(50_000_000)
    if "worldbank" in url and "NY.GDP.PCAP.CD" in url:
        return wb_response(40_000)
    if "open-meteo" in url:
        return meteo_response([25.0] * 60)
    if "api-sports" in url:
        return {"response": []}
    return {}


def test_norm_basic():
    vals = {"a": 10.0, "b": 20.0, "c": 30.0}
    normed = klement._norm(vals)
    assert normed["a"] == pytest.approx(0.0)
    assert normed["c"] == pytest.approx(1.0)
    assert normed["b"] == pytest.approx(0.5)


def test_norm_all_equal():
    vals = {"a": 5.0, "b": 5.0}
    normed = klement._norm(vals)
    assert normed["a"] == pytest.approx(0.5)


def test_elo_update_win():
    new_a, new_b = klement._elo_update(1500.0, 1500.0, "win", k=32)
    assert new_a > 1500.0
    assert new_b < 1500.0


def test_elo_update_draw():
    new_a, new_b = klement._elo_update(1500.0, 1500.0, "draw", k=32)
    assert abs(new_a - 1500.0) < 1.0
    assert abs(new_b - 1500.0) < 1.0


def test_compute_all_writes_files(tmp_path):
    with patch("klement.fetch", side_effect=mock_fetch):
        with patch("klement.KLEMENT_PATH", str(tmp_path / "k.json")):
            with patch("klement.ELO_PATH", str(tmp_path / "e.json")):
                with patch("klement.HISTORICAL_PATH", str(tmp_path / "h.json")):
                    with patch("klement.STORE_PATH", "tests/conftest_fixtures.json"):
                        teams = ["Germany", "France", "Brazil"]
                        with patch("klement.FixtureStore") as MockStore:
                            inst = MockStore.return_value
                            inst.all_teams.return_value = set(teams)
                            klement.compute_all()
                        k = json.loads((tmp_path / "k.json").read_text())
                        e = json.loads((tmp_path / "e.json").read_text())
                        for t in teams:
                            assert t in k
                            assert t in e
                            assert 0.0 <= k[t]["klement_score"] <= 1.0
