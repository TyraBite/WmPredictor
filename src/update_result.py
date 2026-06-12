#!/usr/bin/env python3
"""Usage: python src/update_result.py A1 "2:1" """
import sys
sys.path.insert(0, "src")
from fixtures import FixtureStore
from form_tracker import update_all


def update_result(match_id: str, result: str,
                  fixtures_path: str = "data/fixtures.json") -> None:
    store = FixtureStore(fixtures_path)
    store.load()
    store.set_result(match_id, result)
    update_all(store)
    print(f"✅ {match_id} → {result}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python src/update_result.py <match_id> <result>")
        sys.exit(1)
    update_result(sys.argv[1], sys.argv[2])
