# Prompt: Landing Page Redesign

Implementiere die folgenden Änderungen an `docs/index.html` und `src/update_predictions.py`:

## Backend: `src/update_predictions.py`

1. Lade die alte `docs/predictions.json` vor dem Überschreiben → baue Dict `{match_id → {tip, prob_a, prob_draw, prob_b}}` auf.

2. Für jeden abgeschlossenen Match (`store.completed()`): alten Tipp aus Dict holen (Fallback: frisch vorhersagen). Klassifiziere mutually exclusive (best-first):
   - `correct_result`: tip == result
   - `correct_difference`: Tordifferenz (ta-tb) == (ra-rb), aber nicht exakt
   - `correct_tendency`: Sieger/Unentschieden-Richtung korrekt
   - `wrong`: alles andere
   In `completed_matches`-Liste aufnehmen.

3. Stats aggregieren: `{played, correct_result, correct_difference, correct_tendency, wrong}`

4. Für jeden ausstehenden Match zusätzlich ausgeben:
   - `confidence_level`: `"high"` (max prob ≥55%), `"medium"` (45–55%), `"low"` (<45%)
   - `second_tip`: `top_results[1][0]` (immer mitsenden)

Neues JSON-Schema:
```json
{
  "updated_at": "...", "tournament_phase": "...", "warnings": [],
  "stats": {"played": 0, "correct_result": 0, "correct_difference": 0, "correct_tendency": 0, "wrong": 0},
  "completed_matches": [{"match_id":"A1","group":"A","phase":"group","team_a":"...","flag_a":"...","team_b":"...","flag_b":"...","date":"...","result":"2:0","tip":"1:0","accuracy":"correct_tendency","prob_a":42.5,"prob_draw":27.3,"prob_b":30.2}],
  "pending_matches": [{"...": "bestehende Felder + confidence_level + second_tip"}]
}
```

## Frontend: `docs/index.html`

Layout (oben nach unten):
1. Header + Warning Banner (bestehend)
2. Sektion **HEUTE** — pending matches mit `date == heute`; falls leer: "Heute keine Spiele"
3. Sektion **GESTERN** — completed matches mit `date == gestern`; falls leer: ausblenden
4. Sektion **GENAUIGKEIT** — Stats-Block (nur wenn `played > 0`)
5. Footer

Sektion-Header-Stil: goldene linke Border-Linie, Uppercase-Label, passt zum bestehenden Dark-Theme (`--bg: #1a1a2e`).

**Pending Card Erweiterungen:**
- Confidence Badge oben rechts in `card-meta`: "Sicher" (grün), "Knapp" (gelb), "Unsicher" (rot)
- Bei `confidence_level == "low"`: Zeile "Alt: {second_tip}" gedämpft unter dem Tipp

**Completed Card (neues Design):**
- Ergebnis groß + fett + zentriert
- Darunter: "Tipp war: {tip}" + Accuracy-Badge: "Exakt" (gold), "Differenz ✓" (blau), "Tendenz ✓" (grün), "Daneben" (rot)
- Wahrscheinlichkeits-Bar (readonly)

**Stats-Block:**
- Horizontale Leiste mit 4 farbigen Segmenten (proportional zu played)
- 4 Zahlen: 🏆 Exakt / 📏 Differenz / ↗ Tendenz / ✗ Daneben

Stil: modern, WM-Thema, kein extra Framework — reines HTML/CSS/JS wie bestehend.

## Verifikation
- `pytest` → alle Tests grün
- `python src/update_predictions.py` → JSON hat `stats`, `completed_matches`, `confidence_level`
- `python -m http.server 8080 --directory docs` → 3 Sektionen sichtbar im Browser
