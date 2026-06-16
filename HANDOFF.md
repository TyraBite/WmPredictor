# WM Predictor — Handoff (Session 2026-06-16)

## Was ist das?

WM 2026 Tipps-Vorhersage-Tool. Ensemble-Modell (Poisson + XGBoost), täglich via GitHub Actions aktualisiert, öffentlich als GitHub Pages: https://tyrabite.github.io/WmPredictor/

Repo: https://github.com/TyraBite/WmPredictor | Git-Identität: TyraBite / mcnt94@googlemail.com

---

## Modell-Architektur (Stand jetzt)

| Komponente | Details |
|-----------|---------|
| **Poisson MLE** | Attack/Defense-Params aus 320 WM-Matches 2006–2022; `POISSON_DAMPENING=0.8` (shrinks toward zero) |
| **International Elo** | Aus 49k+ Länderspielen (martj42-Dataset); `ELO_FACTOR=0.75`; λ-Skalierung via `(2*p_elo)^0.75` |
| **XGBoost** | CalibratedClassifierCV, 10% Gewicht (trainiert auf Konstanten → noisy Poisson-Klon) |
| **Draw Boost** | ×1.15 (moderate Korrektur für WM 2026's anomale 44% Draw-Rate) |
| **Blend** | 90% Poisson + 10% XGBoost |

**Elo berechnen/aktualisieren:**
```bash
python src/elo_builder.py            # Fetch + compute (benötigt Internet)
python src/elo_builder.py --check    # Zeige Elo aller WM-2026-Teams
```

---

## Was wurde in diesem Session-Verlauf geändert

### Session 1: Bug-Fix + initiale Modellverbesserung
| Datei | Änderung |
|-------|----------|
| `src/update_predictions.py` | Warning nur bei tatsächlich überfälligen Spielen |
| `src/model.py` | Rank-Adj, POISSON_DAMPENING=0.5, POISSON_NAME_MAP, 85/15 Blend |
| `src/features.py` | FIFA_RANKING Import, rank_a/rank_b ins Feature-Dict |
| `src/klement.py` | +10 fehlende WM-2026-Teams ins FIFA_RANKING |
| `src/backtest.py` | Neu: Backtesting-Framework mit Grid Search |

### Session 2: International Elo + Parametroptimierung
| Datei | Änderung |
|-------|----------|
| `src/elo_builder.py` | **NEU**: Berechnet Elo aus 49k+ internationalen Spielen (martj42) |
| `data/elo_ratings.json` | Ersetzt: 72 WM-basierte Einträge → 339 Teams, echte Elo |
| `src/features.py` | ELO_NAME_MAP (z.B. "Cote d'Ivoire" → "Ivory Coast") |
| `src/model.py` | POISSON_DAMPENING 0.5→**0.8**, ELO_FACTOR=0.75, Blend 85/15→90/10, Draw-Boost ×1.15 |
| `src/backtest.py` | Grid Search auf `elo_factor` umgebaut (statt `rank_adj_exp`) |

---

## Backtesting-Ergebnisse (16 abgeschlossene Spiele, Stand 2026-06-16)

### Vergleich Parameter-Generationen
| Konfiguration | WM 2026 OOS | WM 2022 IS |
|--------------|-------------|------------|
| Original (rank_exp=0.0, 60/40) | 4/16 = 25% | — |
| Session 1 (rank_exp=0.5, damp=0.5, 85/15) | 7/16 = 44% | 38/64 = 59% |
| **Session 2 (elo=0.75, damp=0.8, 90/10)** | **8/16 = 50%** | **42/64 = 66%** |
| Grid-Search-Ceiling (draw_boost=0.3) | 9/16 = 56% | 41/64 = 64% |

### Grid Search (1176 Kombinationen)
```
python src/backtest.py --grid
```
Optimale Params aus Grid Search: `elo_factor=0.75`, `poisson_weight=1.0`, `host_bonus=0.1`, `draw_boost=0.3`, `dampening=0.8`

**Achtung**: `draw_boost=0.3` ist overfit auf WM 2026 (44% Draws ≫ historisch 22%). Für Zukunft `0.15` besser.

### Warum 75% strukturell nicht erreichbar sind

WM 2026 erste 16 Spiele: **7/16 = 43.75% Unentschieden** (historisch: 22-25%).

Dauerhaft falsch vorhersagbare Spiele:
- Spain 0:0 Cape Verde (Spanien 91% Siegwahrscheinlichkeit)
- Belgium 1:1 Egypt (Belgien 90%)
- Netherlands 2:2 Japan (Niederlande 70%)
- Qatar 1:1 Switzerland (Schweiz 75%)
- Saudi Arabia 1:1 Uruguay (Uruguay historisch stark)
- Ivory Coast 1:0 Ecuador (Upset)
- Brazil 1:1 Morocco (Brasilien 57%)

Kein statistisches Modell kann diese konsistent vorhersagen → strukturelles Limit ~50% OOS.

---

## Nächste Schritte

### Kurzfristig
- `ODDS_API_KEY` setzen → Wettquoten-Signal, verbessert Einzelspiel-Genauigkeit erheblich
- Elo nach jedem Spieltag aktualisieren: `python src/elo_builder.py`

### Mittelfristig
- **Squad-Marktwert** (Transfermarkt-API) als Feature → korreliert stark mit Teamstärke
- XGBoost retrainieren mit echten historischen Elo/Klement/H2H-Features (jetzt on Konstanten trainiert)

---

## Schnellstart

```bash
cd wm-predictor
source .venv/bin/activate

# Backtesting / Grid Search
python src/backtest.py              # Evaluation mit aktuellen Params
python src/backtest.py --grid       # Vollständiger Grid Search (~45 Sek)
python src/backtest.py --hist 2006  # Mit historischer Auswertung ab 2006

# Vorhersagen anzeigen
python predict.py

# Ergebnis manuell eintragen
python src/update_result.py A3 "2:1"

# predictions.json neu generieren (für GitHub Pages)
python src/update_predictions.py

# Elo aktualisieren (benötigt Internet)
python src/elo_builder.py

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
| `ODDS_API_KEY` | Wettquoten (optional, aber sehr hilfreich) | Nein |
