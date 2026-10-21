"""
Subgraph-SAT-Solver Experiment Framework

Zentrale Pfade des Projekts. Alle Ergebnisse der Experimente werden
standardmäßig nach ``src/results/`` geschrieben.
"""

from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SRC_DIR / "results"
ISCAS85_DIR = SRC_DIR / "iscas85"


def resolve_output_dir(path=None) -> Path:
    """Löst ein Ausgabeverzeichnis auf.

    - ``None``            -> ``src/results``
    - relativer Pfad      -> relativ zu ``src/results`` (z. B. ``quick`` -> ``src/results/quick``)
    - absoluter Pfad      -> unverändert
    """
    if path is None or str(path) in ("", "."):
        return RESULTS_DIR
    path = Path(path)
    return path if path.is_absolute() else RESULTS_DIR / path
