import json
import sys
import pytest
sys.path.insert(0, "src")
from form_tracker import (
    _turnier_form, _pre_tournament_form, get_adjustment, update_all
)
from fixtures import FixtureStore


FORM_CACHE = {
    "Germany": {"turnier_form": 0.7, "pre_tournament_form": 0.6, "recent_matches": ["W", "L"]},
    "France": {"turnier_form": 0.8, "pre_tournament_form": 0.7, "recent_matches": ["W", "W"]},
}

INJURIES = {"Germany": {"impact_score": -0.10}}


def test_turnier_form_win():
    matches = [{"team_a": "Germany", "team_b": "Japan", "result": "2:0", "status": "completed"}]
    score = _turnier_form("Germany", matches)
    assert score > 0.5


def test_turnier_form_loss():
    matches = [{"team_a": "Germany", "team_b": "Japan", "result": "0:3", "status": "completed"}]
    score = _turnier_form("Germany", matches)
    assert score < 0.5


def test_turnier_form_no_matches():
    assert _turnier_form("Germany", []) == pytest.approx(0.5)


def test_get_adjustment_range(tmp_path):
    fc = tmp_path / "form_cache.json"
    fc.write_text(json.dumps(FORM_CACHE))
    inj = tmp_path / "injuries.json"
    inj.write_text(json.dumps(INJURIES))
    adj = get_adjustment("Germany", form_path=str(fc), injury_path=str(inj))
    assert 0.0 <= adj <= 2.0


def test_get_adjustment_injury_reduces_score(tmp_path):
    fc = tmp_path / "form_cache.json"
    fc.write_text(json.dumps(FORM_CACHE))
    inj_none = tmp_path / "inj_none.json"
    inj_none.write_text(json.dumps({}))
    inj_bad = tmp_path / "inj_bad.json"
    inj_bad.write_text(json.dumps({"Germany": {"impact_score": -0.30}}))
    adj_none = get_adjustment("Germany", form_path=str(fc), injury_path=str(inj_none))
    adj_bad = get_adjustment("Germany", form_path=str(fc), injury_path=str(inj_bad))
    assert adj_bad < adj_none


def test_update_all_writes_cache(tmp_fixtures, tmp_path):
    store = FixtureStore(tmp_fixtures)
    store.load()
    cache_path = str(tmp_path / "form.json")
    update_all(store, form_path=cache_path, injury_path="data/injuries.json")
    data = json.loads(open(cache_path).read())
    assert isinstance(data, dict)
