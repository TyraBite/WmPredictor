import hashlib
import json
import os
import time
from typing import Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
                  raise_on_status=False, read=0, connect=0)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch(url: str, params: dict = None, headers: dict = None,
          ttl_hours: float = 24, cache_dir: str = "data/cache") -> Any:
    os.makedirs(cache_dir, exist_ok=True)
    raw = url + (json.dumps(params, sort_keys=True) if params else "")
    key = hashlib.md5(raw.encode()).hexdigest()
    path = os.path.join(cache_dir, f"{key}.json")

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            entry = json.loads(f.read())
        if (time.time() - entry["_ts"]) / 3600 < ttl_hours:
            return entry["data"]

    resp = _session().get(url, params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"_ts": time.time(), "data": data}))
    return data
