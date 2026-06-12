import json, os
from typing import Optional


class FixtureStore:
    def __init__(self, path: str = "data/fixtures.json"):
        self.path = path
        self._matches: list[dict] = []

    def load(self) -> None:
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Not found: {self.path}")
        self._matches = json.loads(open(self.path).read())

    def save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        open(self.path, "w").write(json.dumps(self._matches, indent=2, ensure_ascii=False))

    def pending(self) -> list[dict]:
        return [m for m in self._matches
                if m.get("status") == "pending"
                and m.get("team_a") is not None
                and m.get("team_b") is not None]

    def completed(self) -> list[dict]:
        return [m for m in self._matches if m.get("status") == "completed"]

    def get(self, match_id: str) -> Optional[dict]:
        return next((m for m in self._matches if m["match_id"] == match_id), None)

    def set_result(self, match_id: str, result: str) -> None:
        m = self.get(match_id)
        if m is None:
            raise KeyError(f"Unknown match_id: {match_id!r}")
        m["status"] = "completed"
        m["result"] = result
        self.save()

    def all_teams(self) -> set[str]:
        teams: set[str] = set()
        for m in self._matches:
            if m.get("team_a"): teams.add(m["team_a"])
            if m.get("team_b"): teams.add(m["team_b"])
        return teams
