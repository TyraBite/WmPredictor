# WM 2026 Predictor

Tiplu-internes WM 2026 Wettbüro-Tool. Zeigt Vorhersagen für ausstehende Spiele basierend auf dem Klement-Modell (Bevölkerung, BIP, Klima, FIFA-Ranking) ergänzt durch Live-Elo-Ratings, Turnierform und Verletzungsanpassungen.

## Setup

```bash
# 1. Abhängigkeiten installieren
pip install -r requirements.txt

# 2. API-Keys konfigurieren
cp .env.example .env
# .env bearbeiten und API_FOOTBALL_KEY eintragen

# 3. Spieldaten laden (einmalig)
python src/bootstrap_fixtures.py

# 4. Statische Scores berechnen (einmalig)
python src/klement.py

# 5. Modell trainieren
python -c "
import sys; sys.path.insert(0,'src')
import json
from model import WMPredictor
matches = json.loads(open('data/historical_matches.json').read())
p = WMPredictor(); p.train(matches); p.save()
"
```

## Tägliche Nutzung

```bash
# Alle ausstehenden Spiele vorhersagen
python predict.py

# Einzelspiel vorhersagen
python predict.py "Germany" "France"

# Ergebnis eintragen (nach dem Spiel)
python src/update_result.py A1 "2:1"

# Verletzung/Sperre melden
python src/add_injury.py "Germany" "Wirtz" injured -0.12

# predictions.json für GitHub Pages regenerieren
python src/update_predictions.py
```

## Automatisierung

GitHub Actions aktualisiert `docs/predictions.json` täglich nach den Spieltagen (19:15 und 22:15 MESZ) und bei jeder Änderung an `data/injuries.json`.

Secrets benötigt: `API_FOOTBALL_KEY`, `ODDS_API_KEY` (optional).

## GitHub Pages

`docs/index.html` lädt `docs/predictions.json` und rendert die Tipps als mobile-optimierte Kartenansicht.
