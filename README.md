# Subgraph-SAT-Solver Experiment Framework

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-36%20passed-4c1)](tests/)
[![Test Coverage](https://img.shields.io/badge/Test%20Coverage-72%25-brightgreen)](doc/coverage/index.html)
[![scicov](https://img.shields.io/badge/scicov-!-ff69b4)](doc/coverage/index.html)

Ein Python-Framework zur Performance-Analyse und Skalierungsuntersuchung von Boolean Circuits unter Verwendung des Subgraph-SAT-Solvers. Das Tool erzeugt CNF-Instanzen aus Circuits, startet beliebig viele Solver auf denselben Dateien, prüft Status und Modelle, aggregiert Statistiken und exportiert LaTeX-kompatible Grafiken und Tabellen für die wissenschaftliche Arbeit unter [science/](science/).

## Inhaltsverzeichnis

- [Features](#features)
- [Projektstruktur](#projektstruktur)
- [Installation](#installation)
- [Verwendung](#verwendung)
- [Instanzen](#instanzen)
- [Messaufbau](#messaufbau)
- [Ergebnisse](#ergebnisse)
- [Auswertung](#auswertung)
- [Tests](#tests)
- [Hinweise](#hinweise)
- [Erwerb](#erwerb)

## Features

- **Verbesserter Messaufbau** (siehe [Messaufbau](#messaufbau)): monotone Nanosekunden-Zeitmessung, Auswertung von Status und Rückgabecode, Modellprüfung gegen CNF und Circuit, Spitzen-Speicherverbrauch, Basislinie (Prozessstart-Grundlast), Median mit Bootstrap-Konfidenzintervall.
- **Experiment-Presets:** `quick` (Funktionstest), `standard`, `full` und `scaling` (bis ca. 10^5 Gates).
- **Vielseitige Instanzen:** Target-AND mit variierenden Eingängen (Exp. 1), Target-AND mit zufälligen Schichten (Exp. 2), ISCAS'85 (Exp. 3), unerfüllbare Miter-Instanzen und große Target-AND-Circuits. Alle mit Ausgangsbedingung (erster Ausgang wahr), siehe [Instanzen](#instanzen).
- **Solver-Vergleich:** Beliebig viele Solver auf denselben CNF-Dateien (Subgraph-SAT-Solver, MiniSat, CaDiCaL, eingebauter Python-Referenzsolver) mit Kreuzvalidierung der Ergebnisse (`solvers_agree`).
- **Referenzsolver:** Kleiner, korrekter CDCL-Solver in reinem Python (`src/reference_solver.py`), der ohne externe Abhängigkeiten läuft und den gesamten Messaufbau testbar macht.
- **Korrigierte CNF-Kodierung:** Tseitin-Kodierung für AND, OR, NOT, NAND, NOR, XOR, XNOR, n-äres XOR und BUFF, gegen die Wahrheitstabellen getestet.
- **Automatische Visualisierung:** Diagramme (SVG/PDF) mit Median, Konfidenzintervall, Netto-Laufzeit und Potenzgesetz-Fit, bei mehreren Solvern zusätzlich ein Solver-Vergleich; `report.txt` nach jedem Durchlauf.
- **Auswertungsskripte für die Arbeit:** `paper_analysis.py` (erste Messreihe) und `paper_analysis_v2.py` (neue Version der Experimente) erzeugen Tabellen (`.tex`), Abbildungen (`.pdf`) und Kennzahlen (`.json`).

## Projektstruktur

```
subgraph-sat-solver-experiments/
├── doc/
│   ├── RESULTS.md              # Auswertung der ersten Messreihe (14.07.2026)
│   └── coverage/               # HTML-Bericht der Testabdeckung
├── science/
│   ├── subgraph-sat-solver-experiments.tex  # Wissenschaftliche Arbeit (LaTeX)
│   └── subgraph-sat-solver-experiments.pdf
├── src/
│   ├── __init__.py             # Zentrale Pfade (results, iscas85), Auflösen von --output-dir
│   ├── boolean_circuits.py     # Circuit-Generatoren, ISCAS'85-Parser, Miter, Circuit-Auswertung
│   ├── cnf.py                  # Tseitin-Kodierung (alle Gate-Typen), DIMACS, Modellprüfung
│   ├── instances.py            # Instanzfamilien, Erwartungswerte und Presets
│   ├── measurement.py          # SolverRunner (Zeit, Speicher, Status), Umgebung, Statistik
│   ├── experiment_runner.py    # Experiment-Suite (Basislinie, Warm-up, Wiederholungen, Verifikation)
│   ├── reference_solver.py     # Kleiner CDCL-Solver in Python als Referenz
│   ├── visualizer.py           # Diagramme und Reports
│   ├── run_experiments.py      # Kommandozeilen-Einstieg
│   ├── quick_start.py          # Interaktives Menü mit Presets
│   ├── paper_analysis.py       # Tabellen und Abbildungen für die erste Messreihe
│   ├── paper_analysis_v2.py    # Tabellen und Abbildungen für die neue Version der Experimente
│   ├── iscas85/                # ISCAS'85 .bench-Dateien (c3 bis c7552)
│   └── results/
│       ├── quick/ standard/ full/ performance/   # Daten der ersten Messreihe
│       ├── full_zwischenstand.csv                # Zwischenstand des Full-Presets (neue Version)
│       ├── full_log_zwischenstand.log            # Konsolenausgabe dazu (mit Basislinien)
│       ├── hardware.md                           # Hardware und Software der Messungen
│       ├── paper/                                # Tabellen, Abbildungen, Kennzahlen für die Arbeit
│       └── v2/<preset>/                          # Standard-Ausgabe neuer Läufe
├── tests/                      # Unit- und Integrationstests (unittest)
├── LICENSE
├── README.md
└── pyproject.toml
```

## Installation

```bash
git clone https://github.com/naphez86/subgraph-sat-solver-experiments.git
cd subgraph-sat-solver-experiments
pip install -e .
```

**Voraussetzungen:**
- Python ≥ 3.10
- numpy ≥ 1.24.0, matplotlib ≥ 3.7.0
- Kompilierte `SubgraphSATSolver` (bzw. `SubgraphSATSolver.exe`) – im `PATH` oder per `--solver-path`. Zum Testen des Messaufbaus genügt `--with-reference` (Python-Referenzsolver, keine Messaussage über den Subgraph-SAT-Solver)
- Optional: `psutil` (Arbeitsspeicher in `environment.json`), MiniSat oder CaDiCaL als Vergleichssolver

**Extras:**

| Extra | Installation | Inhalt |
|-------|--------------|--------|
| `dev` | `pip install -e ".[dev]"` | psutil, pytest, pytest-cov |
| `paper` | `pip install -e ".[paper]"` | pandas, scipy (für `paper_analysis.py`) |

Ohne `pip install` genügt es, die Befehle aus dem Projektwurzelverzeichnis auszuführen (`python -m src...`).

## Verwendung

Alle Befehle werden im Projektwurzelverzeichnis ausgeführt.

```bash
# Interaktives Menü mit Presets
python -m src.quick_start

# Funktionstest des Messaufbaus mit dem eingebauten Referenzsolver
python -m src.run_experiments --preset quick --solver-path "" --with-reference

# Standard-Preset mit Subgraph-SAT-Solver, MiniSat und Referenzsolver auf denselben Instanzen
python -m src.run_experiments --preset standard --solver-path build/SubgraphSATSolver \
    --with-solver minisat --with-reference

# Full-Preset (Exp. 1-3, Miter, Skalierung) mit Subgraph-SAT-Solver und Referenzsolver
python -m src.run_experiments --preset full --solver-path build/SubgraphSATSolver --with-reference

# Skalierung bis 10^5 Gates, 20 Wiederholungen, 120 s Timeout
python -m src.run_experiments --preset scaling --repetitions 20 --timeout 120

# Ein Solver mit Argumenten (Kommando als Zeichenkette)
python -m src.run_experiments --preset quick --solver-path "SubgraphSATSolver --subgraph-binary ./subgraph"

# Vorhandene Ergebnisse neu visualisieren
python -m src.run_experiments --visualize src/results/v2/quick/experiment_results.json

# Referenzsolver direkt auf einer DIMACS-Datei
python -m src.reference_solver instanz.cnf
```

### Kommandozeilenoptionen

| Option | Bedeutung |
|--------|-----------|
| `--preset {quick,standard,full,scaling}` | Experiment-Preset (Standard: `standard`) |
| `--benchmark-suite` | Exp. 1-3 mit den Parametern von `standard`, ohne Miter und Skalierung |
| `--full-suite` | Alias für `--preset full` |
| `--solver-path CMD` | Hauptsolver: Pfad oder Kommando mit Argumenten; leer = keiner |
| `--with-solver CMD` | Zusätzlicher Vergleichssolver, mehrfach angebbar (z. B. `minisat`, `cadical`) |
| `--with-reference` | Python-CDCL-Referenzsolver (Label `reference-cdcl`) hinzufügen |
| `--repetitions N`, `--warmup N`, `--timeout S` | Überschreiben die Werte des Presets |
| `--output-dir DIR` | Ausgabeverzeichnis, siehe [Ergebnisse](#ergebnisse) |
| `--visualize JSON` | Diagramme aus einer vorhandenen `experiment_results.json` neu erzeugen |
| `--formats svg pdf png` | Export-Formate der Diagramme (Standard: `svg pdf`) |
| `--skip-visualization` | Keine Diagramme nach dem Lauf |

Die Labels der Solver müssen eindeutig sein. Ein nicht startbarer Solver wird gemeldet und übersprungen. Der Prozess-Rückgabecode ist 0, wenn alle Läufe zum erwarteten Ergebnis passen und alle Modelle gültig sind; sonst 1 (kein Solver verfügbar: 2).

### Presets

| Preset | Instanzen | Wiederholungen | Warm-up | Timeout | Inhalt |
|--------|-----------|----------------|---------|---------|--------|
| `quick` | 12 | 5 | 1 | 20 s | wenige Instanzen aus Exp. 1-3 und Miter |
| `standard` | 42 | 15 | 2 | 30 s | Exp. 1-3 und Miter |
| `full` | 46 | 30 | 3 | 60 s | Exp. 1-3, Miter und vier Skalierungsinstanzen (m = 100, 1000, 10 000, 50 000) |
| `scaling` | 7 | 10 | 2 | 120 s | Target-AND mit m = 100, 500, 1000, 5000, 10 000, 20 000, 50 000 (bis ca. 10^5 Gates) |

Die Anzahl der Wiederholungen wird zusätzlich durch das Zeitbudget je Instanz begrenzt (mindestens 3), siehe [Messaufbau](#messaufbau).

## Instanzen

Alle Instanzen verwenden die Ausgangsbedingung (`constraint="output"`): Der erste Ausgang des Circuits wird per Unit-Klausel auf wahr gesetzt. Die Formeln sind damit nicht mehr trivial erfüllbar. Wo die Antwort aus der Konstruktion folgt, ist sie als Erwartungswert hinterlegt und wird gegen das Ergebnis geprüft (`correct`).

| Familie | Inhalt | Erwartet |
|---------|--------|----------|
| `target_and` | Exp. 1: Target-AND mit m = 4, 6, ..., 20 Eingängen | SAT (eindeutige Belegung) |
| `target_and_random` | Exp. 2: Target-AND (m = 10) mit Tiefe d = 1, ..., 12 zufälliger Schichten | nicht vorab bekannt |
| `iscas85` | Exp. 3: die zwölf ISCAS'85-Circuits (c3 bis c7552) | nicht vorab bekannt |
| `miter_self` | Circuit gegen eine Kopie seiner selbst (Target-AND m = 10, 20; c17, c432, c499, c880, c1355, c1908) | UNSAT |
| `miter_equiv` | c499 gegen die funktional äquivalente Variante c1355 | UNSAT |
| `scaling` | Target-AND mit großem m (bis 50 000, bis ca. 10^5 Gates) | SAT |

Die Formel eines Target-AND-Circuits mit m ≥ 2 Eingängen und Ausgangsbedingung hat `3m-1` Variablen, `5m-2` Klauseln und `11m-6` Literalvorkommen. Ein Miter enthält die Gates beider Circuits und zusätzlich XOR- und ODER-Gates (`MiterSelf_c1908`: 1 786 Gates, c1908 selbst: 880).

## Messaufbau

Umsetzung der sieben Vorschläge aus der wissenschaftlichen Arbeit (Abschnitt „Verbesserungen des Messaufbaus"):

| Nr. | Vorschlag | Umsetzung |
|-----|-----------|-----------|
| 1 | Korrekte Kodierung von NAND, NOR, XOR | `src/cnf.py`; zusätzlich XNOR, n-äres XOR, BUFF; Test gegen die Wahrheitstabellen (`tests/test_cnf.py`) |
| 2 | Auswertung von Rückgabecode und Ausgabe | `parse_solver_output`: Status `SAT`, `UNSAT`, `UNKNOWN`, `TIMEOUT`, `ERROR`, `NO_OUTPUT`; Modell wird gegen CNF und Circuit geprüft |
| 3 | Hochauflösende Zeitmessung, Basislinie | `time.perf_counter_ns`, solverinterne Zeit (falls ausgegeben), `baseline.json`, Spalte `runtime_net_ms` |
| 4 | Mehr Wiederholungen, Warm-up, Median und CI | Presets, `summary.csv` mit Median, Quartilen und Bootstrap-Konfidenzintervall |
| 5 | Ausgangsbedingung, unerfüllbare Instanzen, große Circuits | `constraint="output"`, Miter-Instanzen (`build_miter`), Target-AND bis 10^5 Gates |
| 6 | Umgebung und Speicher | `environment.json`, Spitzen-RSS je Lauf (`memory_usage_mb`) |
| 7 | Vergleich mit etablierten Solvern | `--with-solver`, `--with-reference`; Kreuzvalidierung (`solvers_agree`) |

**Ablauf je Instanz und Solver:** Das Framework schreibt eine DIMACS-Datei und startet den Solver als eigenen Prozess. Die Laufzeit umfasst Prozessstart, Einlesen, Lösen und Prozessende. Zuerst laufen die Warm-up-Läufe (verworfen), dann `n = max(3, min(Wiederholungen, Zeitbudget / t_Warm-up))` gemessene Läufe. Berichtet wird der Median. Endet schon ein Warm-up-Lauf mit `TIMEOUT`, `ERROR` oder `NO_OUTPUT`, wird die Instanz nur einmal gemessen (n = 1); der Wert ist dann ein einzelner Messwert und keine Median-Schätzung. Zu Beginn eines Presets wird je Solver die Basislinie gemessen (30 Läufe mit einer trivialen Instanz); sie ist die Prozessstart-Grundlast in allen Laufzeiten.

**Statusbestimmung:** Maßgeblich sind in dieser Reihenfolge eine `s`-Zeile im SAT-Competition-Format, die Zeile `Status:` des Subgraph-SAT-Solvers, eine alleinstehende Ergebniszeile und zuletzt der Rückgabecode (10: SAT, 20: UNSAT). Ein Rückgabecode außerhalb von {0, 10, 20} ergibt `ERROR`.

Weitere Korrekturen: Der ISCAS'85-Parser sortiert Gates topologisch, meldet undefinierte Signale und Zyklen als Fehler und behält Ein-/Ausgangsnamen (nötig für den Miter); die Ergebniserkennung wertet keine Banner-Zeilen wie `Reduction: SAT → Subgraph-Isom` mehr als `SAT`.

## Ergebnisse

Alle Ergebnisse werden nach `src/results/` geschrieben. `--output-dir` mit einem relativen Pfad gilt relativ zu `src/results/`, ein absoluter Pfad wird unverändert verwendet. Ohne `--output-dir` landen Läufe unter `src/results/v2/<preset>/`; die Daten der ersten Messreihe (`quick/`, `standard/`, `full/`, `performance/`) bleiben unberührt.

Je Lauf-Verzeichnis:

| Datei | Inhalt |
|-------|--------|
| `experiment_results.csv/.json` | ein Eintrag je gemessenem Lauf (u. a. Status, Rückgabecode, Laufzeit, Netto-Laufzeit, Speicher, Modellprüfung) |
| `summary.csv/.json` | Kennzahlen je Solver und Instanz (Median, Quartile, CI, Status, Korrektheit, Solver-Übereinstimmung) |
| `environment.json` | Betriebssystem, CPU, Python, Timer, Solver und Versionen |
| `baseline.json` | Prozessstart-Grundlast je Solver (triviale Instanz) |
| `config.json` | Preset, Wiederholungen, Timeout |
| `plots/` | Diagramme (SVG/PDF) und `report.txt` |

### Erste Messreihe (14.07.2026)

Daten unter `src/results/{quick,standard,full,performance}/` (288 Läufe, alte Kodierung, `time.time()`, ohne Ergebniserfassung). Sie sind als Messartefakt zu lesen: Die Laufzeiten sind von Prozessstart und grober Zeitauflösung dominiert und unabhängig von der Instanzgröße. Ausführliche Auswertung in [doc/RESULTS.md](doc/RESULTS.md) und in der Arbeit ([science/](science/)).

### Neue Version der Experimente (Version 3.0.0, Zwischenstand vom 11.10.2026)

Ausgeführt mit dem verbesserten Messaufbau auf einer virtuellen Maschine mit einer CPU und 3,9 GiB Arbeitsspeicher ([src/results/hardware.md](src/results/hardware.md)), Full-Preset mit Subgraph-SAT-Solver und Referenzsolver. Der Lauf wurde bei `TargetAND_m10000` abgebrochen; ausgewertet sind 44 der 46 Instanzen anhand von [`full_zwischenstand.csv`](src/results/full_zwischenstand.csv) (nur Mediane, keine Einzelläufe) und [`full_log_zwischenstand.log`](src/results/full_log_zwischenstand.log).

| Kennzahl | Wert |
|----------|------|
| Basislinie (Prozessstart) | Subgraph-SAT-Solver 8,43 ms, Referenzsolver 56,18 ms |
| Referenzsolver | löst alle 44 Instanzen, bis auf die größeren Miter nahe an der Basislinie (41 bis 102 ms) |
| Subgraph-SAT-Solver | Ergebnis bei 33, Timeout (60 s) bei 5, `ERROR` bei 6 Instanzen |
| Übereinstimmung | in allen 33 Fällen, in denen beide Solver entscheiden, gleiches Ergebnis; alle bekannten Erwartungswerte getroffen |
| Größte gelöste Instanz | c2670 (1 193 Gates, 7 422 Literale): 20,4 s |
| Skalierung (ISCAS'85) | Exponent 2,08 ± 0,07 über der Literalzahl (6 Punkte, c432 bis c2670), gilt für die gesamte Pipeline |
| Ausfälle | alle `ERROR` und Timeouts ab 10 487 Literalen; Ursache nicht untersucht |

Grenzen dieser Daten: Es liegen nur Mediane vor (keine Streumaße), der Referenzsolver ist ein Python-Programm ohne Anspruch auf Geschwindigkeit und sagt nichts über MiniSat oder CaDiCaL aus, die Kreuzung der Laufzeitkurven bei ca. 400 Literalen ist vor allem ein Effekt der unterschiedlichen Startkosten, und die Skalierungsinstanzen m = 10 000 und m = 50 000 fehlen. Die Einordnung steht im Abschnitt „Neue Version der Experimente" der Arbeit (dort noch als Version 2.0.0 bezeichnet).

## Auswertung

Die Arbeit unter [science/](science/) enthält beide Messreihen. Tabellen und Abbildungen werden aus den Ergebnisdateien erzeugt und unter `src/results/paper/` abgelegt (`summary.json` bzw. `summary_v2.json` enthalten alle im Text genannten Kennzahlen):

```bash
# Erste Messreihe (Daten aus src/results/{quick,standard,full,performance})
pip install -e ".[paper]"
python -m src.paper_analysis

# Neue Version der Experimente (Daten aus src/results/full_zwischenstand.csv und full_log_zwischenstand.log)
python -m src.paper_analysis_v2

# PDF der Arbeit
cd science && pdflatex subgraph-sat-solver-experiments.tex
```

`paper_analysis_v2.py` berechnet die Struktur der Instanzen (Variablen, Klauseln, Literale) mit den Generatoren des Frameworks neu und erzeugt `fig_v2_*.pdf`, `tab_v2_*.tex` und `summary_v2.json`. Ein vollständiger neuer Lauf, der den Zwischenstand ersetzt, wird mit `python -m src.run_experiments --preset full --solver-path <Pfad> --with-reference` gestartet.

## Tests

```bash
python -m unittest discover -s tests -t .
```

Mit pytest und Coverage (`pip install -e ".[dev]"`):

```bash
pytest
```

`pytest` schreibt den HTML-Bericht nach `doc/coverage/`. Die Tests decken Kodierung (`test_cnf.py`), Circuits und Miter (`test_circuits.py`), Messaufbau (`test_measurement.py`) sowie Experiment-Suite und Referenzsolver (`test_experiments.py`) ab.

## Hinweise

- Der Solver liefert Rückgabecode 20 auch bei `UNKNOWN` und bei Fehlern. Der Messaufbau wertet deshalb die Zeile `Status:` der Ausgabe aus.
- Der Solver setzt nach einem positiven Subgraph-Ergebnis alle Variablen auf wahr (siehe README des Solvers). Für Circuit-Formeln besteht diese Belegung die Validierung in der Regel nicht; solche Läufe erscheinen als `ERROR` und nicht als `SAT`.
- Die Kodierung mit Ausgangsbedingung hat für Target-AND-Circuits `5m-2` statt `6m-4` Klauseln (die redundante AND-Klausel entfällt, dazu kommt die Unit-Klausel des Ausgangs). Satz 1 der Arbeit gilt für die Kodierung der ersten Messreihe, Satz 2 für die neue Version.
- Der Solver wurde für die Messungen mit `g++ -O2` gebaut; die CMake-Konfiguration des Solvers setzt `-O3 -march=native`. Messwerte aus beiden Builds sind nur eingeschränkt vergleichbar.

## Erwerb

Der Preis für diese Software beträgt 7.145.000,00 EUR.

### Zahlungsinformationen

Name: Stephan Epp  
IBAN: DE24 5003 1900 0012 5603 20  
BIC: BBVADEFFXXX
