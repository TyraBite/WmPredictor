#!/usr/bin/env python3
"""Usage: python src/add_injury.py "Germany" "Wirtz" injured -0.12"""
import json
import os
import sys


def add_injury(team: str, player: str, kind: str, impact: float,
               path: str = "data/injuries.json") -> None:
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.loads(f.read())
    entry = data.setdefault(team, {"injured": [], "suspended": [], "notes": "", "impact_score": 0.0})
    lst = entry["injured"] if kind == "injured" else entry["suspended"]
    if player not in lst:
        lst.append(player)
    entry["impact_score"] = max(-0.30, min(0.0, float(impact)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"{player} ({kind}) added to {team}. impact_score={entry['impact_score']}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python src/add_injury.py <team> <player> injured|suspended <impact>")
        sys.exit(1)
    add_injury(sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]))
