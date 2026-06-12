import json, pytest, sys; sys.path.insert(0, "src")
from fixtures import FixtureStore


def test_load_reads_json(tmp_fixtures):
    s = FixtureStore(tmp_fixtures); s.load()
    assert len(s._matches) == 3


def test_pending_excludes_completed_and_null_teams(tmp_fixtures):
    s = FixtureStore(tmp_fixtures); s.load()
    p = s.pending()
    assert len(p) == 1
    assert p[0]["match_id"] == "A1"


def test_completed_returns_completed(tmp_fixtures):
    s = FixtureStore(tmp_fixtures); s.load()
    assert [m["match_id"] for m in s.completed()] == ["A2"]


def test_get_returns_match(tmp_fixtures):
    s = FixtureStore(tmp_fixtures); s.load()
    assert s.get("A2")["result"] == "2:1"
    assert s.get("NOPE") is None


def test_set_result_persists(tmp_fixtures):
    s = FixtureStore(tmp_fixtures); s.load()
    s.set_result("A1", "3:0")
    s2 = FixtureStore(tmp_fixtures); s2.load()
    m = s2.get("A1")
    assert m["status"] == "completed"
    assert m["result"] == "3:0"


def test_set_result_missing_raises(tmp_fixtures):
    s = FixtureStore(tmp_fixtures); s.load()
    with pytest.raises(KeyError):
        s.set_result("NOPE", "1:0")


def test_all_teams_excludes_none(tmp_fixtures):
    s = FixtureStore(tmp_fixtures); s.load()
    teams = s.all_teams()
    assert None not in teams
    assert "Germany" in teams and "France" in teams
