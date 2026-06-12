import hashlib, json, os, time
from typing import Any
import requests


def fetch(url: str, params: dict = None, headers: dict = None,
          ttl_hours: float = 24, cache_dir: str = "data/cache") -> Any:
    os.makedirs(cache_dir, exist_ok=True)
    raw = url + (str(sorted(params.items())) if params else "")
    key = hashlib.md5(raw.encode()).hexdigest()
    path = os.path.join(cache_dir, f"{key}.json")

    if os.path.exists(path):
        entry = json.loads(open(path).read())
        if (time.time() - entry["_ts"]) / 3600 < ttl_hours:
            return entry["data"]

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    open(path, "w").write(json.dumps({"_ts": time.time(), "data": data}))
    return data
