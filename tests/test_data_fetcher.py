import hashlib, json, time, os
from unittest.mock import patch, MagicMock
import pytest
import sys; sys.path.insert(0, "src")
from data_fetcher import fetch


def cache_key(url, params=None):
    raw = url + (str(sorted(params.items())) if params else "")
    return hashlib.md5(raw.encode()).hexdigest()


def test_fresh_cache_skips_http(tmp_path):
    url = "https://example.com"
    key = cache_key(url)
    f = tmp_path / f"{key}.json"
    f.write_text(json.dumps({"_ts": time.time(), "data": {"x": 1}}))
    with patch("data_fetcher.requests.get") as m:
        result = fetch(url, cache_dir=str(tmp_path))
        m.assert_not_called()
    assert result == {"x": 1}


def test_expired_cache_refetches(tmp_path):
    url = "https://example.com"
    key = cache_key(url)
    f = tmp_path / f"{key}.json"
    f.write_text(json.dumps({"_ts": time.time() - 90000, "data": {"old": True}}))
    resp = MagicMock(); resp.json.return_value = {"new": True}; resp.raise_for_status.return_value = None
    with patch("data_fetcher.requests.get", return_value=resp):
        result = fetch(url, cache_dir=str(tmp_path))
    assert result == {"new": True}


def test_no_cache_fetches_and_writes(tmp_path):
    url = "https://example.com/new"
    resp = MagicMock(); resp.json.return_value = {"ok": True}; resp.raise_for_status.return_value = None
    with patch("data_fetcher.requests.get", return_value=resp):
        result = fetch(url, cache_dir=str(tmp_path))
    assert result == {"ok": True}
    key = cache_key(url)
    assert (tmp_path / f"{key}.json").exists()


def test_headers_passed_to_requests(tmp_path):
    url = "https://example.com/h"
    hdrs = {"x-api-key": "s3cr3t"}
    resp = MagicMock(); resp.json.return_value = {}; resp.raise_for_status.return_value = None
    with patch("data_fetcher.requests.get", return_value=resp) as m:
        fetch(url, headers=hdrs, cache_dir=str(tmp_path))
    assert m.call_args[1]["headers"] == hdrs
