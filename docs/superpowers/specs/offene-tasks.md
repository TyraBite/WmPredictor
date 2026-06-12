# Ausstehende Aufgaben — WM Predictor

Alle offenen Tasks in Reihenfolge. Jeder Block ist eigenständig und kann direkt umgesetzt werden.

---

## Task 1: Odds-Namenskorrektur committen

**Status:** Code geschrieben, noch nicht committed.

**Was:** `src/features.py` hat bereits die `ODDS_NAME_MAP` und die Normalisierung in `_odds_probs()`. Nur noch committen.

**Verifikation:** `git diff src/features.py` zeigt die Map, dann `git commit`.

---

## Task 2: Auto-Fetch in `predict.py`

**Was:** `predict.py` soll automatisch `fetch_results()` aufrufen wenn pending Matches ein Datum ≤ heute haben und `FOOTBALL_DATA_KEY` gesetzt ist.

**Änderung in `predict.py` → `main()`**, direkt nach `store.load()`:

```python
from datetime import date as _date

def _needs_result_fetch(store) -> bool:
    today = _date.today().isoformat()
    return any(m["date"] <= today for m in store.pending())
```

```python
# in main(), nach store.load():
if _needs_result_fetch(store) and os.environ.get("FOOTBALL_DATA_KEY"):
    print("🔄 Neue Ergebnisse werden abgerufen...")
    from fetch_results import fetch_results
    fetch_results()
    store.load()
```

**Verhalten:**
- Key gesetzt + vergangene Pending-Matches → auto-fetch, dann Predictions
- Key fehlt → Warnung wie bisher, kein Fetch
- Alle Matches in der Zukunft → kein Fetch
- Idempotent (TTL-Cache 1h + Status-Check in fetch_results)

**Verifikation:** `python predict.py` mit vergangenen Pending-Matches gibt "🔄 Neue Ergebnisse..." aus.

---

## Task 3: Landing Page Redesign

### 3a: Backend — `src/update_predictions.py`

1. **Alte predictions.json laden** vor dem Überschreiben → Dict `{match_id → {tip, prob_a, prob_draw, prob_b}}`

2. **Abgeschlossene Matches** (`store.completed()`) klassifizieren (mutually exclusive, best-first):
   - `correct_result`: tip == result (exakt)
   - `correct_difference`: Tordifferenz (ta-tb) == (ra-rb), aber nicht exakt
   - `correct_tendency`: Sieger/Unentschieden-Richtung korrekt
   - `wrong`: alles andere
   → In `completed_matches`-Liste aufnehmen mit: match_id, group, phase, team_a/b, flag_a/b, date, result, tip, accuracy, prob_a/draw/b

3. **Stats aggregieren:** `{played, correct_result, correct_difference, correct_tendency, wrong}`

4. **Pending Matches** um folgende Felder erweitern:
   - `confidence_level`: `"high"` (max prob ≥55%), `"medium"` (45–55%), `"low"` (<45%)
   - `second_tip`: `top_results[1][0]`

**Neues predictions.json-Schema:**
```json
{
  "updated_at": "...", "tournament_phase": "...", "warnings": [],
  "stats": {"played": 0, "correct_result": 0, "correct_difference": 0, "correct_tendency": 0, "wrong": 0},
  "completed_matches": [{
    "match_id": "A1", "group": "A", "phase": "group",
    "team_a": "Mexico", "flag_a": "🇲🇽", "team_b": "Poland", "flag_b": "🇵🇱",
    "date": "2026-06-11", "result": "2:0", "tip": "1:0",
    "accuracy": "correct_tendency", "prob_a": 42.5, "prob_draw": 27.3, "prob_b": 30.2
  }],
  "pending_matches": [{"...alle bestehenden Felder...", "confidence_level": "low", "second_tip": "1:1"}]
}
```

### 3b: Frontend — `docs/index.html`

**Layout (oben nach unten):**
1. Header + Warning Banner (bestehend)
2. Sektion **HEUTE** — pending matches mit `date == heute`; falls leer: "Heute keine Spiele"
3. Sektion **GESTERN** — completed matches mit `date == gestern`; falls leer: ausblenden
4. Sektion **GENAUIGKEIT** — Stats-Block (nur wenn `played > 0`)
5. Footer

**Sektion-Header-Stil:** Goldene linke Border-Linie (`border-left: 3px solid var(--accent)`), Uppercase-Label, passt zum bestehenden Dark-Theme.

**Pending Card Erweiterungen:**
- Confidence Badge in `card-meta` (inline pill): "Sicher" (grün), "Knapp" (gelb), "Unsicher" (rot)
- Bei `confidence_level == "low"`: Zeile `Alt: {second_tip}` gedämpft unter dem Tipp

**Completed Card (neues Design):**
- Ergebnis groß + fett + zentriert
- Darunter: "Tipp war: {tip}" + Accuracy-Badge: "Exakt" (gold), "Differenz ✓" (blau), "Tendenz ✓" (grün), "Daneben" (rot)
- Wahrscheinlichkeits-Bar (readonly, zeigt Modell-Einschätzung)

**Stats-Block:**
- Horizontale Leiste mit 4 farbigen Segmenten (proportional zu `played`)
- 4 Kennzahlen: 🏆 Exakt / 📏 Differenz / ↗ Tendenz / ✗ Daneben

**Stil:** Reines HTML/CSS/JS, kein Framework, WM-Thema, Dark Mode wie bestehend.

**Verifikation:**
- `pytest` → alle Tests grün
- `python src/update_predictions.py` → JSON hat `stats`, `completed_matches`, `confidence_level`
- `python -m http.server 8080 --directory docs` → 3 Sektionen im Browser sichtbar

---

## Task 4: `.pkl` aus `.gitignore` nehmen (optional)

**Was:** `data/model_xgb.pkl` ist gitignored — GitHub Actions hat das XGBoost-Modell nicht und fällt auf Poisson-only zurück.

**Entscheidung offen:** Datei ins Repo aufnehmen (~wenige MB) oder Poisson-only für Prod akzeptieren?
