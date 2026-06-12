# WM 2026 Predictor

Tiplu-internes WM 2026 Wettbüro-Tool. Zeigt Vorhersagen für ausstehende Spiele basierend auf dem Klement-Modell (Bevölkerung, BIP, Klima, FIFA-Ranking) ergänzt durch Live-Elo-Ratings, Turnierform und Verletzungsanpassungen.

---

## Voraussetzungen

- Python 3.11 oder neuer
- Ein kostenloser football-data.org-Account (siehe unten)
- Optional: ein Odds-API-Account für Wettquoten (kann übersprungen werden)

---

## API-Keys beschaffen

### football-data.org (Pflicht)

Der Key wird für den Spielplan-Abruf und täglich zum Laden aktueller Ergebnisse verwendet. Außerdem lädt er historische WM-Daten (2006–2022) für das Vorhersagemodell.

1. Gehe auf [football-data.org](https://www.football-data.org/client/register) und registriere dich
2. Der Key kommt per E-Mail — kein Kreditkarte nötig
3. Den Key als `FOOTBALL_DATA_KEY` in `.env` eintragen (siehe Setup-Schritt 2)

> **Hinweis:** Der kostenlose Plan reicht für den Betrieb aus. Das Tool cached alle Antworten 24 Stunden in `data/cache/`, sodass API-Anfragen auf ein Minimum reduziert werden.

### Odds API (Optional)

Ohne diesen Key zeigt das Tool statt echter Wettquoten neutrale Standardwerte (40%/25%/35%). Das Modell funktioniert vollständig ohne ihn.

1. Gehe auf [the-odds-api.com](https://the-odds-api.com) und erstelle einen kostenlosen Account
2. Den API Key aus dem Dashboard kopieren und als `ODDS_API_KEY` in `.env` eintragen

---

## Setup (einmalig)

### Schritt 1 — Repository klonen und Abhängigkeiten installieren

```bash
git clone <repo-url>
cd wm-predictor
```

Virtuelle Umgebung anlegen und Abhängigkeiten installieren:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Danach ist `python` im Terminal immer das aus der aktivierten venv. Die venv muss in jeder neuen Terminal-Session erneut aktiviert werden (`activate`). Alternativ kann jeder Befehl direkt mit `.venv\Scripts\python` (Windows) bzw. `.venv/bin/python` (Linux/macOS) aufgerufen werden.

### Schritt 2 — API-Keys konfigurieren

**Windows:**
```powershell
copy .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

Dann `.env` mit einem Texteditor öffnen und die Keys eintragen:

```
FOOTBALL_DATA_KEY=dein_key_hier
ODDS_API_KEY=dein_key_hier   # kann leer bleiben
```

### Schritt 3 — Spieldaten laden

Dieser Schritt ruft die football-data.org-API einmalig ab und speichert alle WM-2026-Spielpaarungen (Gruppenphase + KO-Bracket) in `data/fixtures.json`.

```bash
python src/bootstrap_fixtures.py
```

Erwartete Ausgabe:
```
Written 72 group + 32 KO slots → data/fixtures.json
```

Die 48 Gruppenspiele enthalten bereits Teams, Datum und Spielort. Die 32 KO-Slots sind als Platzhalter angelegt und werden automatisch befüllt, sobald die Gruppenphase durch ist.

### Schritt 4 — Statische Scores und Elo-Ratings ~~berechnen~~ (entfällt)

`data/klement_scores.json` und `data/elo_ratings.json` sind bereits im Repository enthalten. Dieser Schritt ist nicht mehr nötig.

> `src/klement.py` bleibt im Repo falls die Daten nach einer Regeländerung (FIFA-Ranking, neue WM-Ergebnisse) neu berechnet werden sollen.

### Schritt 5 — Vorhersagemodell trainieren

Das Modell (Poisson-MLE + XGBoost-Ensemble) wird auf den historischen WM-Daten aus Schritt 4 trainiert und anschließend gespeichert.

```bash
python -c "
import sys; sys.path.insert(0, 'src')
import json
from model import WMPredictor
matches = json.load(open('data/historical_matches.json'))
print(f'Trainiere auf {len(matches)} Spielen...')
p = WMPredictor()
p.train(matches)
p.save()
print('Modell gespeichert.')
"
```

Erwartete Ausgabe:
```
Trainiere auf N Spielen...
Modell gespeichert.
```

Erzeugte Dateien:
- `data/model_poisson.json` — Poisson-Parameter (Angriffs-/Defensivstärke pro Team)
- `data/model_xgb.pkl` — trainierter XGBoost-Klassifikator

Das Setup ist damit abgeschlossen.

---

## Tägliche Nutzung

### Vorhersagen anzeigen

```bash
# Alle ausstehenden Spiele (nach Datum sortiert)
python predict.py

# Ein einzelnes Spiel
python predict.py "Germany" "France"
```

`predict.py` ruft automatisch Ergebnisse ab, wenn `FOOTBALL_DATA_KEY` gesetzt ist und vergangene Spiele noch als ausstehend markiert sind. Ein manueller Abruf ist daher in der Regel nicht nötig.

### Ergebnis nach einem Spiel eintragen

Die Match-ID steht in der Ausgabe von `predict.py` und entspricht dem Schema `A1`, `B3`, `R32_4` etc.

```bash
python src/update_result.py A1 "2:1"
```

Das Ergebnis wird in `data/fixtures.json` gespeichert und die Turnierform aller Teams sofort neu berechnet.

### Verletzung oder Sperre melden

```bash
# Verletzter Spieler (impact_score zwischen 0.0 und -0.30)
python src/add_injury.py "Germany" "Wirtz" injured -0.12

# Gesperrter Spieler
python src/add_injury.py "France" "Mbappe" suspended -0.20
```

Der `impact_score` gibt an, wie stark das Team durch den Ausfall geschwächt wird. Als Richtwert:
- `-0.05` bis `-0.10` — Stammkraft fehlt, Ersatz vorhanden
- `-0.12` bis `-0.20` — wichtiger Spieler, spürbare Schwächung
- `-0.20` bis `-0.30` — Schlüsselspieler (Top-Torschütze, Stammkeeper)

### predictions.json für GitHub Pages aktualisieren

```bash
python src/update_predictions.py
```

Dies regeneriert `docs/predictions.json`, die von der Web-App geladen wird. Sollte nach jedem eingetragenen Ergebnis und nach jeder Verletzungsmeldung ausgeführt werden.

---

## Automatisierung via GitHub Actions

Wenn das Repository auf GitHub liegt, übernehmen zwei Workflows die automatische Aktualisierung:

- **`update_after_matchday.yml`** — läuft täglich um 19:15 und 22:15 MESZ, holt Spielergebnisse von football-data.org und regeneriert `docs/predictions.json`
- **`injury_update.yml`** — läuft automatisch, sobald `data/injuries.json` gepusht wird

### Secrets im Repository hinterlegen

Im GitHub-Repository unter **Settings → Secrets and variables → Actions** folgende Secrets anlegen:

| Secret | Wert | Pflicht |
|--------|------|---------|
| `FOOTBALL_DATA_KEY` | Key aus football-data.org | Ja |
| `ODDS_API_KEY` | Key aus the-odds-api.com | Nein |

---

## GitHub Pages aktivieren

1. Im GitHub-Repository unter **Settings → Pages**
2. **Source:** `Deploy from a branch`
3. **Branch:** `main`, Ordner: `/docs`
4. Speichern — die App ist dann unter `https://<username>.github.io/<repo>/` erreichbar

Die Web-App lädt automatisch `docs/predictions.json` und ist in drei Sektionen gegliedert:

| Sektion | Inhalt |
|---------|--------|
| **HEUTE** | Mindestens 3 ausstehende Spiele — zuerst die heutigen, dann die nächsten. Anstoßzeit in der lokalen Zeitzone des Browsers. Jede Karte zeigt die 3 wahrscheinlichsten Ergebnisse sowie ein Confidence-Badge (Sicher / Knapp / Unsicher). |
| **GESTERN** | Abgeschlossene Spiele vom Vortag mit Ergebnis und Accuracy-Badge (Exakt / Differenz ✓ / Tendenz ✓ / Daneben). Wird ausgeblendet wenn leer. |
| **GENAUIGKEIT** | Gesamtstatistik aller getippten Spiele als farbige Leiste und Kennzahlen. Wird erst angezeigt wenn mindestens ein Spiel gespielt wurde. |

---

## Projektstruktur

```
wm-predictor/
├── src/
│   ├── bootstrap_fixtures.py   # Einmalig: WM-Spielplan von API-Football laden
│   ├── klement.py              # Einmalig: Klement-Scores + Elo-Ratings berechnen
│   ├── data_fetcher.py         # HTTP-Client mit 24h-Cache
│   ├── fixtures.py             # Spielplan lesen/schreiben (FixtureStore)
│   ├── form_tracker.py         # Turnierform + Live-Anpassung berechnen
│   ├── features.py             # Feature-Vektor für Vorhersagemodell bauen
│   ├── model.py                # Poisson-MLE + XGBoost-Ensemble (WMPredictor)
│   ├── fetch_results.py        # Täglich: aktuelle Ergebnisse abrufen
│   ├── update_result.py        # Manuell: Ergebnis eintragen
│   ├── update_predictions.py   # predictions.json regenerieren
│   └── add_injury.py           # Verletzung/Sperre melden
├── predict.py                  # CLI-Einstiegspunkt
├── data/
│   ├── fixtures.json           # Spielplan + Status (Bootstrap-Output)
│   ├── injuries.json           # Manuelle Verletzungsdaten
│   ├── klement_scores.json     # Klement-Scores (klement.py-Output)
│   ├── elo_ratings.json        # Elo-Ratings (klement.py-Output)
│   ├── historical_matches.json # Historische WM-Daten 2006–2022 (im Repo enthalten)
│   ├── form_cache.json         # Turnierform-Cache (automatisch)
│   └── cache/                  # HTTP-Response-Cache (automatisch, .gitignore)
├── docs/
│   ├── index.html              # GitHub Pages Web-App
│   └── predictions.json        # Vorhersage-Output (update_predictions.py)
└── .github/workflows/          # GitHub Actions
```
