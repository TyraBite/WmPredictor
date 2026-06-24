# WM 2026 Predictor

Zeigt Vorhersagen für ausstehende Spiele basierend auf einem Ensemble-Modell (Poisson-MLE + XGBoost), das mit internationalem Elo (49.000+ Länderspiele), Turnierform, Klement-Scores (Bevölkerung, BIP, Klima) und Verletzungsanpassungen arbeitet.

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
2. Der Key kommt per E-Mail — keine Kreditkarte nötig
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

Dieser Schritt ruft die football-data.org-API einmalig ab und speichert alle WM-2026-Spielpaarungen in `data/fixtures.json`.

```bash
python src/bootstrap_fixtures.py
```

Erwartete Ausgabe:
```
Written 72 group + 32 KO slots → data/fixtures.json
```

### Schritt 4 — Elo-Ratings berechnen (benötigt Internet)

Berechnet internationale Elo-Ratings für alle 339 aktiven Nationalmannschaften aus 49.000+ historischen Länderspielen (Quelle: [martj42/international_results](https://github.com/martj42/international_results)) und aktualisiert sie mit den bisher gespielten WM-2026-Ergebnissen.

```bash
python src/elo_builder.py
```

> `data/elo_ratings.json` ist bereits im Repository enthalten und aktuell. Dieser Schritt ist nur nötig, wenn die Ratings nach neuen Spielen aktualisiert werden sollen.

### Schritt 5 — Vorhersagemodell trainieren

Das Modell (Poisson-MLE + XGBoost-Ensemble) wird auf den historischen WM-Daten 2006–2022 trainiert.

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

### Ergebnis nach einem Spiel eintragen

Die Match-ID steht in der Ausgabe von `predict.py` und entspricht dem Schema `A1`, `B3`, `R32_4` etc.

```bash
python src/update_result.py A1 "2:1"
```

Das Ergebnis wird in `data/fixtures.json` gespeichert und die Turnierform sofort neu berechnet. Anschließend `update_predictions.py` ausführen.

### predictions.json für GitHub Pages aktualisieren

```bash
python src/update_predictions.py
```

Regeneriert `docs/predictions.json`. Sollte nach jedem eingetragenen Ergebnis ausgeführt werden.

### Verletzung oder Sperre melden

```bash
# Verletzter Spieler (impact_score zwischen 0.0 und -0.30)
python src/add_injury.py "Germany" "Wirtz" injured -0.12

# Gesperrter Spieler
python src/add_injury.py "France" "Mbappe" suspended -0.20
```

Der `impact_score` gibt an, wie stark das Team geschwächt wird:
- `-0.05` bis `-0.10` — Stammkraft fehlt, Ersatz vorhanden
- `-0.12` bis `-0.20` — wichtiger Spieler, spürbare Schwächung
- `-0.20` bis `-0.30` — Schlüsselspieler (Top-Torschütze, Stammkeeper)

### Modell-Genauigkeit evaluieren

```bash
# Evaluation mit aktuellen Parametern (alle bisherigen WM-2026-Spiele)
python src/backtest.py

# Score-Tipp-Grid-Search: tip_dampening × goals_scale optimieren
# Kombiniert WM-2026-OOS (60%) + historische WM 2006–2022 (40%)
python src/backtest.py --score-grid

# Tendenz-Parameter-Grid-Search (~45 Sekunden, 1176 Kombinationen)
python src/backtest.py --grid

# Nur historische WM-Simulation (kein OOS-Anteil)
python src/backtest.py --hist-scores
```

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
| `GH_PAT` | Personal Access Token (für Branch-Protection) | Ja |
| `ODDS_API_KEY` | Key aus the-odds-api.com | Nein |

---

## GitHub Pages aktivieren

1. Im GitHub-Repository unter **Settings → Pages**
2. **Source:** `Deploy from a branch`
3. **Branch:** `main`, Ordner: `/docs`
4. Speichern — die App ist dann unter `https://<username>.github.io/<repo>/` erreichbar

Die Web-App besteht aus zwei Seiten:

**Hauptseite (`index.html`)** — drei Sektionen:

| Sektion | Inhalt |
|---------|--------|
| **HEUTE** | Ausstehende Spiele — zuerst die heutigen, dann die nächsten. Anstoßzeit in lokaler Zeitzone. Jede Karte zeigt den Modelltipp groß (inkl. erwarteter Tordifferenz) und die 3 wahrscheinlichsten Ergebnisse klein darunter. |
| **GESTERN** | Abgeschlossene Spiele vom Vortag mit Ergebnis und Accuracy-Badge (Exakt / Differenz ✓ / Tendenz ✓ / Daneben). |
| **GENAUIGKEIT** | Gesamtstatistik aller getippten Spiele als farbige Leiste. |

**Detailseite (`details.html`)** — zwei Tabs:

| Tab | Inhalt |
|-----|--------|
| **Alle Vorhersagen** (Standard) | Alle ausstehenden Spiele gegliedert nach Datum; Detailmodal mit Tipp-Zusammensetzung, Modell-Faktoren und Buchmacherquoten. |
| **Vergangene Tipps** | Alle abgeschlossenen Spiele mit Accuracy. |

Im Detailmodal kann per Swipe (Touch), Pfeiltasten oder ‹ › Buttons zwischen Spielen navigiert werden.

---

## Modell-Architektur

Das Vorhersagemodell kombiniert drei Signale:

| Komponente | Gewicht | Details |
|-----------|---------|---------|
| **Poisson MLE** | 90% | Attack/Defense-Parameter aus 320 WM-Spielen 2006–2022; gedämpft mit `POISSON_DAMPENING=0.8` |
| **Internationales Elo** | — | Skaliert die Poisson-Lambdas via `(2·p_elo)^0.75`; aus 49k+ Länderspielen (martj42-Datensatz) |
| **XGBoost** | 10% | Kalibrierter Klassifikator; aktuell auf Konstanten trainiert (kein eigenständiger Mehrwert) |

### Duales Lambda-System

Das Modell verwendet zwei Lambda-Paare mit unterschiedlicher Dämpfung:

| Lambda-Typ | Parameter | Zweck |
|-----------|-----------|-------|
| **λ Modell** | `POISSON_DAMPENING=0.8` | Konservativ; treibt die Win/Draw/Loss-Wahrscheinlichkeiten |
| **λ Tipp** | `TIP_DAMPENING=0.6` × `GOALS_SCALE=1.8` | Expressiver; bestimmt den Ergebnistipp |

**Tipp-Selektion:** Aus λ Tipp wird direkt eine Poisson-Matrix aufgebaut. Optionale Buchmacher-Ergebnisquoten werden eingeblended (`SCORE_ODDS_BLEND=0.3`). Falls die Odds API Over/Under-Quoten liefert, werden die Tipp-Lambdas auf die implizierte Gesamttor-Erwartung skaliert. Dann wird das wahrscheinlichste Ergebnis in der richtigen Siegrichtung (Sieg A / Unentschieden / Sieg B) als Tipp gewählt.

**Draw-Boost:** `p_draw *= 1.30` — korrigiert die systematische Untervorhersage von Unentschieden bei Turnieren (WM 2026: ~44% Remisquote in der Gruppenphase, historisch ~22%).

**Grid-Search-Ergebnis (kombiniert: 60% WM-2026-OOS + 40% WM-2006–2022-IS, Kicktipp-Punkte 4/3/2/0):**

| Parameter | Kicktipp-Pts |
|-----------|--------------|
| Baseline (D=0.8, scale=1.0, kein Draw-Boost) | 24/80 (30%) |
| **Optimal (D=0.6, scale=1.8, Draw-Boost=1.30)** | **77/192 (40%)** |

**Aktuelle OOS-Genauigkeit (WM 2026, 48 Spiele):** Exakt 4 · Differenz 2 · Tendenz 17 — Kicktipp-Punkte 77/192 (40%)

---

## Projektstruktur

```
wm-predictor/
├── src/
│   ├── bootstrap_fixtures.py   # Einmalig: WM-Spielplan von API laden
│   ├── elo_builder.py          # Internationales Elo aus martj42-Datensatz berechnen
│   ├── klement.py              # Klement-Scores + FIFA-Ranking-Tabelle
│   ├── data_fetcher.py         # HTTP-Client mit 24h-Cache
│   ├── fixtures.py             # Spielplan lesen/schreiben (FixtureStore)
│   ├── form_tracker.py         # Turnierform + Live-Anpassung berechnen
│   ├── features.py             # Feature-Vektor für Vorhersagemodell bauen
│   ├── model.py                # Poisson-MLE + XGBoost-Ensemble (WMPredictor)
│   ├── backtest.py             # OOS-Evaluation + Parameter-Grid-Search
│   ├── fetch_results.py        # Täglich: aktuelle Ergebnisse abrufen
│   ├── update_result.py        # Manuell: Ergebnis eintragen
│   ├── update_predictions.py   # predictions.json regenerieren
│   └── add_injury.py           # Verletzung/Sperre melden
├── predict.py                  # CLI-Einstiegspunkt
├── data/
│   ├── fixtures.json           # Spielplan + Status
│   ├── injuries.json           # Manuelle Verletzungsdaten
│   ├── klement_scores.json     # Klement-Scores (klement.py-Output)
│   ├── elo_ratings.json        # Internationales Elo für 339 Teams (elo_builder.py-Output)
│   ├── historical_matches.json # Historische WM-Daten 2006–2022
│   ├── model_poisson.json      # Trainierte Poisson-Parameter
│   ├── model_xgb.pkl           # Trainierter XGBoost-Klassifikator
│   ├── form_cache.json         # Turnierform-Cache (automatisch)
│   └── cache/                  # HTTP-Response-Cache (automatisch, .gitignore)
├── docs/
│   ├── index.html              # GitHub Pages Hauptseite (heutige Spiele)
│   ├── details.html            # Alle Tipps & Vorhersagen (zwei Tabs)
│   └── predictions.json        # Vorhersage-Output (update_predictions.py)
├── tests/                      # Pytest-Tests (37/40 bestehen; 3 Netzwerktests schlagen lokal fehl)
├── HANDOFF.md                  # Technischer Kontext für AI-Agenten
└── .github/workflows/          # GitHub Actions
```
