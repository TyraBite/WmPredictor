import hashlib
import json
import os
import time
from typing import Any
import requests


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

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"_ts": time.time(), "data": data}))
    return data
