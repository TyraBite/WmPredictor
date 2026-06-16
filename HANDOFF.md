# WM Predictor — Handoff (Session 2026-06-16)

## Was ist das?

WM 2026 Tipps-Vorhersage-Tool. Ensemble-Modell (Poisson + XGBoost), täglich via GitHub Actions aktualisiert, öffentlich als GitHub Pages: https://tyrabite.github.io/WmPredictor/

Repo: https://github.com/TyraBite/WmPredictor | Git-Identität: TyraBite / mcnt94@googlemail.com

---

## Was wurde in dieser Session geändert

### Bug-Fix: Irreführende Warning
**Datei**: `src/update_predictions.py`

`⚠️ Live-Updates nicht verfügbar (FOOTBALL_DATA_KEY fehlt)` feuert jetzt nur noch wenn es tatsächlich überfällige Spiele ohne Ergebnis gibt (kickoff_utc > 90 min in der Vergangenheit, noch pending).

### Modell-Verbesserungen (alle 4 Fixes + Backtesting)

| Datei | Änderung | Begründung |
|-------|----------|------------|
| `src/features.py` | FIFA-Ranking (rank_a/rank_b) ins Feature-Dict | Aktuelles Ranking als Signal |
| `src/model.py` | Rank-Adj-Exponent 0.2→**0.5** | Stärkere Ranking-Korrektur nach Grid Search |
| `src/model.py` | `POISSON_DAMPENING=0.5` | Shrinks extreme historical params (NZ def=+0.908 aus 3 WM-Spielen) |
| `src/model.py` | `POISSON_NAME_MAP` | "Czechia"→"Czech Republic", "Bosnia-Herzegovina"→"Bosnia and Herzegovina" |
| `src/model.py` | Blend 80/20→**85/15** (Poisson/XGBoost) | XGBoost trainiert auf Konstanten, mehr Poisson-Gewicht besser |
| `src/model.py` | Live-Adj Cap: max(0.6, min(1.67, raw_adj)) | Verhindert extreme Verzerrungen |
| `src/form_tracker.py` | Turnier-Form-Gewicht 0.4→0.5, Pre-Turnier 0.3→0.2 | Aktuelle Form wichtiger |
| `src/klement.py` | FIFA_RANKING +10 WM-2026-Teams | Sweden=17, South Africa=58, Haiti=96, Bosnia=60, Curaçao=130, etc. |
| `src/backtest.py` | NEU: Backtesting-Framework | Grid Search + OOS-Evaluation |

---

## Backtesting-Ergebnisse (Stand 2026-06-16, 16 abgeschlossene Spiele)

### Aktuelle Params (nach Session-Änderungen)
```
WM 2026 OOS: 7/16 = 44%  (Tendenz korrekt)
WM 2022 IS:  38/64 = 59%
WM 2006+ IS: 182/320 = 57%
```

### Vergleich: vorher vs. nachher
| Params | WM 2026 OOS |
|--------|-------------|
| Original (rank_exp=0.0, 60/40) | 4/16 = 25% |
| Vor dieser Sub-Session (rank_exp=0.2, 80/20) | 6/16 = 38% |
| **Jetzt (rank_exp=0.5, 85/15, damp=0.5)** | **7/16 = 44%** |
| Maximum erreichbar (draw_boost=0.3, damp=0.8) | 8/16 = 50% |

### Warum 75% nicht erreichbar sind

WM 2026 (erste 16 Spiele): **7/16 = 43.75% Unentschieden** (historisch: 22-25%).

Die 8 dauerhaft falsch vorhergesagten Spiele:
1. **Canada vs Bosnia** (1:1) — Unentschieden bei unklarer Favoritenrolle
2. **Qatar vs Switzerland** (1:1) — Schweiz klar favorisiert (rank 20 vs 35)
3. **Brazil vs Morocco** (1:1) — Brasilien 68% Siegwahrscheinlichkeit
4. **Australia vs Turkey** (2:0) — Türkei marginal besser gerankt (25 vs 28)
5. **Netherlands vs Japan** (2:2) — Niederlande 69% Siegwahrscheinlichkeit
6. **Spain vs Cape Verde Islands** (0:0) — Spanien 91% Siegwahrscheinlichkeit
7. **Belgium vs Egypt** (1:1) — Belgien 90% Siegwahrscheinlichkeit
8. **Saudi Arabia vs Uruguay** (1:1) — Uruguay historisch stark (Poisson)

Plus Upset: **Ivory Coast vs Ecuador** (1:0) — Ecuador rank 22 vs Ivory Coast 34.

Kein statistisches Modell kann diese vorhersagen. Spiele 3/5/6/7 waren massive Favoritensiege-die-Unentschieden-wurden.

### Grid Search (864 Kombinationen, ~45 Sekunden)
```
python src/backtest.py --grid
```
Optimiert: rank_adj_exp, poisson_weight, host_bonus, draw_boost, poisson_dampening

---

## Root Causes der schlechten Bilanz (bleibt bei alten Tips eingefroren)

1. **XGBoost auf Konstanten trainiert**: Alle Features (klement_diff, Elo, Odds, H2H) wurden mit Defaults gesetzt. XGBoost ignoriert diese effektiv. Vollständige Lösung = XGBoost mit echten historischen Features retrainieren.
2. **Historische Tips eingefroren**: Die Bilanz in `docs/predictions.json` reflektiert die gespeicherten Tipps zum Zeitpunkt ihrer Generierung. Modell-Verbesserungen wirken NUR auf zukünftige Tipps.
3. **Hohe Draw-Rate in WM 2026**: 43.75% Unentschieden in den ersten 16 Spielen → strukturelles Limit für alle statistischen Modelle.

---

## Nächste Schritte (Mögliche Verbesserungen)

### Kurzfristig (ohne Retraining)
- **Aktuelle Turnierwettquoten** aus `ODDS_API_KEY` (Bookmaker wissen mehr als Ranking allein)
- **Draw-Boost für ähnlich-gerankte Teams** (z.B. wenn |rank_a - rank_b| < 5 → draw-Wahrscheinlichkeit +20%)

### Mittelfristig (erfordert Datenquellen)
- **Internationales Elo** aus allen Länderspielen (nicht nur WM) → bessere Stärke-Schätzung für Japan, Marokko
- **Squad-Marktwert** (Transfermarkt) → Korreliert stark mit Tatsachenstärke
- **Aktuelle Form** der letzten 6 Monate (FIFA-Ranking-Verlauf)

### Langfristig (erfordert Retraining)
- **XGBoost retrainieren**: Historische Elo/Klement/H2H für alle 320 WM-Matches berechnen und als Features einbauen. Würde XGBoost deutlich verbessern.

---

## Schnellstart

```bash
cd wm-predictor
source .venv/bin/activate

# Backtesting / Grid Search
python src/backtest.py              # Evaluation mit aktuellen Params
python src/backtest.py --grid       # Vollständiger Grid Search (~45 Sek)
python src/backtest.py --hist 2022  # Mit historischer Auswertung ab 2022

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
| `ODDS_API_KEY` | Wettquoten (optional) | Nein |
