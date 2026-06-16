# WM Predictor — Handoff (Session 2026-06-16)

## Was ist das?

WM 2026 Tipps-Vorhersage-Tool. Ensemble-Modell (Poisson + XGBoost), täglich via GitHub Actions aktualisiert, öffentlich als GitHub Pages: https://tyrabite.github.io/WmPredictor/

Repo: https://github.com/TyraBite/WmPredictor | Git-Identität: TyraBite / mcnt94@googlemail.com

---

## Was wurde in dieser Session geändert

### Bug-Fix: Irreführende Warning
**Datei**: `src/update_predictions.py`

Vorher feuerte `⚠️ Live-Updates nicht verfügbar (FOOTBALL_DATA_KEY fehlt)` immer, wenn der API-Key fehlte — auch wenn alle Ergebnisse manuell gepflegt waren. Jetzt nur noch wenn es tatsächlich überfällige Spiele ohne Ergebnis gibt (kickoff_utc > 90 min in der Vergangenheit, noch pending).

### Modell-Verbesserungen (alle 4 Fixes zusammen)

| Datei | Änderung | Begründung |
|-------|----------|------------|
| `src/features.py` | FIFA-Ranking (rank_a/rank_b) ins Feature-Dict | Aktuelles Ranking als Signal |
| `src/model.py` | Poisson-λ skaliert mit `((51-rank_a)/(51-rank_b))^0.2` | Elo aus hist. Daten war falsch kalibriert (USA Elo 1481 < Paraguay Elo 1491, obwohl FIFA-Rang 11 vs 44) |
| `src/model.py` | Blend-Gewicht 60/40 → 80/20 (Poisson/XGBoost) | XGBoost war mit konstanten Features trainiert (klement_diff=0, elo=1500 für ALLE 320 Trainingsspiele) → konnte diese Features nicht gewichten |
| `src/model.py` | Live-Adj Cap: raw_adj → max(0.6, min(1.67, raw_adj)) | Verhindert extreme Verzerrungen bei früher Formabweichung |
| `src/form_tracker.py` | Turnier-Form-Gewicht 0.4 → 0.5, Pre-Turnier 0.3 → 0.2 | Aktuelle Turnierleistung ist aussagekräftiger |

**Konkreter Effekt**: USA vs Paraguay (USA gewann 4:1) war vorher 17.1% für USA vs 49.2% Paraguay. Nach dem Fix: 42.7% USA vs 19.5% Paraguay.

---

## Aktuelle Bilanz (Stand 2026-06-14, 9 Spiele)

| Kategorie | Alt |
|-----------|-----|
| Exakt ✅ | 0 |
| Differenz 📏 | 0 |
| Tendenz ↗ | 2 |
| Daneben ✗ | 7 |

Die Bilanz für abgeschlossene Spiele bleibt historisch (Tips werden bei Spielabschluss eingefroren). Verbesserungen wirken nur auf zukünftige Tipps.

---

## Bekannte Root Causes der schlechten Bilanz

1. **XGBoost auf Konstanten trainiert**: Nur attack/defense variierten in Training-Features. Alle anderen Features (klement_diff, Elo, Odds, H2H) wurden mit Defaults gesetzt → XGBoost ignoriert diese effektiv. Vollständige Lösung = XGBoost mit echten historischen Features retrainieren.
2. **Historisches Elo ≠ 2026 Stärke**: Wurde durch FIFA-Ranking-Korrektur in Poisson abgemildert.
3. **Teamname-Mapping**: "United States" ↔ "USA", "Czechia" ↔ "Czech Republic" etc. — ODDS_NAME_MAP wird jetzt auch für FIFA_RANKING-Lookup verwendet.

---

## Nächste Schritte (optional)

- **XGBoost retrainieren mit echten Features**: Historische Elo/Klement/H2H für alle 320 WM-Matches berechnen und damit trainieren. Würde XGBoost deutlich verbessern.
- **FIFA_RANKING aktualisieren**: Ranking-Dict in `klement.py` (Zeilen 78-91) manuell auf aktuellen Stand bringen (aktuell: Stand ~2024/2025).
- **Ranking-Exponent tunen**: Aktuell 0.2 (konservativ). Nach mehr Spielen Backtesting möglich.

---

## Schnellstart

```bash
cd wm-predictor
source .venv/bin/activate

# Vorhersagen anzeigen
python predict.py

# Ergebnis manuell eintragen
python src/update_result.py A3 "2:1"

# predictions.json neu generieren (für GitHub Pages)
python src/update_predictions.py

# Tests
python -m pytest tests/ -q
# Erwartung: 37/40 grün (3 pre-existing failures in test_data_fetcher.py)

# Lokale Vorschau
python -m http.server 8080 --directory docs
# → http://localhost:8080
```

---

## Secrets

| Secret | Zweck | Pflicht |
|--------|-------|---------|
| `FOOTBALL_DATA_KEY` | Ergebnis-Abruf von football-data.org | Für Auto-Updates ja |
| `GH_PAT` | GitHub Actions Push (Branch-Protection) | Ja |
| `ODDS_API_KEY` | Wettquoten (optional, free tier liefert correct_score ggf. nicht) | Nein |
