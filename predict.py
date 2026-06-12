#!/usr/bin/env python3
"""
WM 2026 Predictor CLI.

Usage:
  python predict.py                     # all pending matches
  python predict.py "Germany" "France"  # single match
"""
import os
import sys
import json
from datetime import date as _date
sys.path.insert(0, "src")
from dotenv import load_dotenv
load_dotenv()


def _needs_result_fetch(store) -> bool:
    today = _date.today().isoformat()
    return any(m["date"] <= today for m in store.pending())


WIDTH = 43


def _box(lines: list[str]) -> str:
    top = "┌" + "─" * (WIDTH - 2) + "┐"
    bot = "└" + "─" * (WIDTH - 2) + "┘"
    rows = [top]
    for line in lines:
        pad = WIDTH - 4 - len(line)
        rows.append("│  " + line + " " * max(0, pad) + "  │")
    rows.append(bot)
    return "\n".join(rows)


def _form_emoji(recent: list[str]) -> str:
    icons = {"W": "✅W", "D": "🟡D", "L": "❌L"}
    return "  ".join(icons.get(r, r) for r in recent)


def _strength_label(score: float) -> str:
    if score >= 0.75:
        return "sehr stark"
    if score >= 0.55:
        return "stark"
    if score >= 0.45:
        return "mittel"
    return "schwach"


def _injuries_line(team: str, injuries: dict) -> str:
    entry = injuries.get(team, {})
    parts = [f"{p} ❌" for p in entry.get("injured", [])]
    parts += [f"{p} 🟥" for p in entry.get("suspended", [])]
    return ", ".join(parts) if parts else "Keine Ausfälle"


def _format_date(date_str: str) -> str:
    months = ["", "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
              "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    try:
        y, m, d = date_str.split("-")
        return f"{int(d)}. {months[int(m)]} {y}"
    except Exception:
        return date_str


def predict_match(match: dict, predictor, form_cache: dict, injuries: dict,
                  klement_scores: dict) -> str:
    from features import build
    feat = build(match["team_a"], match["team_b"], match["venue"])
    feat["attack_a"] = predictor._poisson_params.get(match["team_a"], {}).get("attack", 0)
    feat["defense_a"] = predictor._poisson_params.get(match["team_a"], {}).get("defense", 0)
    feat["attack_b"] = predictor._poisson_params.get(match["team_b"], {}).get("attack", 0)
    feat["defense_b"] = predictor._poisson_params.get(match["team_b"], {}).get("defense", 0)
    r = predictor.predict(feat, match["team_a"], match["team_b"])

    ka = klement_scores.get(match["team_a"], {}).get("klement_score", 0)
    kb = klement_scores.get(match["team_b"], {}).get("klement_score", 0)
    fa = form_cache.get(match["team_a"], {}).get("recent_matches", [])
    fb = form_cache.get(match["team_b"], {}).get("recent_matches", [])
    adj_a = form_cache.get(match["team_a"], {}).get("turnier_form", 0.5)
    adj_b = form_cache.get(match["team_b"], {}).get("turnier_form", 0.5)

    phase = match.get("group", "?")
    date_label = _format_date(match["date"])
    flag_a = match.get("flag_a", "")
    flag_b = match.get("flag_b", "")

    lines = [
        f"{flag_a} {match['team_a']} vs {match['team_b']} {flag_b}",
        f"📅 {date_label} | Gruppe {phase}",
        "",
        f"Sieg {match['team_a']:<14} {r.prob_a * 100:5.1f}%",
        f"Unentschieden        {r.prob_draw * 100:5.1f}%",
        f"Sieg {match['team_b']:<14} {r.prob_b * 100:5.1f}%",
        "",
        f"Wahrscheinlichstes Ergebnis: {r.tip}",
        "Top 3 Ergebnisse:",
    ] + [f"  {sc}  → {p * 100:4.1f}%" for sc, p in r.top_results] + [
        "",
        "📊 Klement-Score:",
        f"  {match['team_a']}: {ka:.2f} | {match['team_b']}: {kb:.2f}",
        "",
        "🔥 Turnier-Form:",
        f"  {match['team_a']}: {_form_emoji(fa)}  ({_strength_label(adj_a)})",
        f"  {match['team_b']}: {_form_emoji(fb)}  ({_strength_label(adj_b)})",
        "",
        "🚑 Verletzungen/Sperren:",
        f"  {match['team_a']}: {_injuries_line(match['team_a'], injuries)}",
        f"  {match['team_b']}: {_injuries_line(match['team_b'], injuries)}",
    ]
    return _box(lines)


def main():
    from fixtures import FixtureStore
    from model import WMPredictor

    warnings = []
    if not os.environ.get("ODDS_API_KEY"):
        warnings.append("⚠️  ODDS_API_KEY nicht gesetzt – Wettquoten deaktiviert.")
    if not os.environ.get("FOOTBALL_DATA_KEY"):
        warnings.append("⚠️  FOOTBALL_DATA_KEY nicht gesetzt – keine Live-Updates möglich.")

    for w in warnings:
        print(w)

    predictor = WMPredictor()
    try:
        predictor.load()
    except FileNotFoundError:
        print("❌ Kein trainiertes Modell gefunden. Bitte erst: python src/klement.py")
        sys.exit(1)

    store = FixtureStore()
    try:
        store.load()
    except FileNotFoundError:
        print("❌ fixtures.json nicht gefunden. Bitte erst: python src/bootstrap_fixtures.py")
        sys.exit(1)

    if _needs_result_fetch(store) and os.environ.get("FOOTBALL_DATA_KEY"):
        print("🔄 Neue Ergebnisse werden abgerufen...")
        from fetch_results import fetch_results
        fetch_results()
        store.load()

    form_cache = {}
    if os.path.exists("data/form_cache.json"):
        with open("data/form_cache.json", encoding="utf-8") as f:
            form_cache = json.loads(f.read())
    injuries = {}
    if os.path.exists("data/injuries.json"):
        with open("data/injuries.json", encoding="utf-8") as f:
            injuries = json.loads(f.read())
    klement_scores = {}
    if os.path.exists("data/klement_scores.json"):
        with open("data/klement_scores.json", encoding="utf-8") as f:
            klement_scores = json.loads(f.read())

    if len(sys.argv) == 3:
        team_a, team_b = sys.argv[1], sys.argv[2]
        match = next((m for m in store.pending()
                      if m["team_a"] == team_a and m["team_b"] == team_b), None)
        if not match:
            match = {
                "match_id": "CUSTOM", "group": "?", "phase": "custom",
                "team_a": team_a, "team_b": team_b,
                "flag_a": "", "flag_b": "", "date": "", "venue": "New York/NJ",
                "status": "pending", "result": None,
            }
        print(predict_match(match, predictor, form_cache, injuries, klement_scores))
    else:
        pending = store.pending()
        if not pending:
            print("✅ Keine ausstehenden Spiele mehr.")
            return
        print(f"\n{'=' * WIDTH}")
        print(f"  WM 2026 — {len(pending)} ausstehende Spiele")
        print(f"{'=' * WIDTH}\n")
        for match in pending:
            print(predict_match(match, predictor, form_cache, injuries, klement_scores))
            print()


if __name__ == "__main__":
    main()
