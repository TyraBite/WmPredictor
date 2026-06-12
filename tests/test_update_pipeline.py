import json
import os
import sys
from unittest.mock import patch, MagicMock
import pytest
sys.path.insert(0, "src")
from update_result import update_result
from fixtures import FixtureStore


def test_update_result_marks_completed(tmp_fixtures):
    update_result("A1", "2:1", fixtures_path=tmp_fixtures)
    s = FixtureStore(tmp_fixtures)
    s.load()
    m = s.get("A1")
    assert m["status"] == "completed"
    assert m["result"] == "2:1"


def test_update_result_unknown_match_raises(tmp_fixtures):
    with pytest.raises(KeyError):
        update_result("NOPE", "1:0", fixtures_path=tmp_fixtures)


def test_update_predictions_writes_json(tmp_fixtures, tmp_path):
    from update_predictions import build_predictions_json
    out = str(tmp_path / "predictions.json")
    build_predictions_json(
        fixtures_path=tmp_fixtures,
        output_path=out,
        form_path="data/form_cache.json",
        injury_path="data/injuries.json",
        klement_path="data/klement_scores.json",
    )
    with open(out, encoding="utf-8") as f:
        data = json.loads(f.read())
    assert "updated_at" in data
    assert "pending_matches" in data
    assert "warnings" in data
    assert isinstance(data["pending_matches"], list)
