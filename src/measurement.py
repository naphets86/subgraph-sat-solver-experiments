"""
Messaufbau für Solver-Läufe.

Verbesserungen gegenüber der ersten Messreihe:

- Zeitmessung mit ``time.perf_counter_ns`` (monoton, Nanosekunden-Auflösung)
  statt ``time.time()``.
- Rückgabecode und Ausgabe des Solvers werden ausgewertet; Status ist einer
  von ``SAT``, ``UNSAT``, ``TIMEOUT``, ``ERROR``, ``NO_OUTPUT``. Ein Lauf ohne
  erkennbares Ergebnis wird als ``NO_OUTPUT`` markiert und nicht als
  ``False`` gewertet. (``"SAT" in output`` traf zuvor auch auf ``UNSAT`` zu.)
- Modelle (``v``-Zeilen) werden gegen die CNF geprüft.
- Spitzen-Speicherverbrauch des Solver-Prozesses (``wait4``/``ru_maxrss``).
- Basislinie: Laufzeit einer trivialen Instanz (Prozessstart-Grundlast).
- Erfassung der Umgebung (Betriebssystem, CPU, Python, Solver-Version, Git).
- Statistik je Instanz: Median, Quartile, Bootstrap-Konfidenzintervalle.
"""

import json
import os
import platform
import re
import shlex
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from src import SRC_DIR
from src.cnf import CNF, check_model, parse_model

PROJECT_ROOT = SRC_DIR.parent

STATUSES = ("SAT", "UNSAT", "UNKNOWN", "TIMEOUT", "ERROR", "NO_OUTPUT")
TRIVIAL_CNF = "p cnf 2 2\n1 2 0\n-1 2 0\n"

# SAT-Competition-Format: "s SATISFIABLE" usw.
_RE_S_LINE = re.compile(r"^s\s+(SATISFIABLE|UNSATISFIABLE|UNKNOWN|INDETERMINATE)\b", re.M | re.I)
# Ausgabeformat des Subgraph-SAT-Solvers (SATSolverResult::to_string): "Status: SATISFIABLE"
_RE_STATUS_LINE = re.compile(r"^Status:\s*(SATISFIABLE|UNSATISFIABLE|UNKNOWN|ERROR)\b", re.M | re.I)
# MiniSat u. a.: das Ergebnis steht allein in einer Zeile. Freie Textsuche nach "SAT"
# ist bewusst nicht erlaubt (Banner wie "Reduction: SAT -> Subgraph" würden treffen).
_RE_BARE_LINE = re.compile(r"^\s*(SAT|SATISFIABLE|UNSAT|UNSATISFIABLE)\s*$", re.M | re.I)
_RE_TOTAL_TIME = re.compile(r"\bTotal time:\s*([0-9]+(?:\.[0-9]+)?)\s*(ms|s)?\b", re.I)
_RE_TIME = re.compile(r"\btime\b[^0-9\n]{0,20}([0-9]+(?:\.[0-9]+)?)\s*(ms|s|sec|seconds)?", re.I)
_RE_ASSIGN = re.compile(r"^Assignment:\s*\{(.*)\}", re.M)
_RE_ASSIGN_ITEM = re.compile(r"x(\d+)\s*=\s*([TF])")

_WORD_TO_STATUS = {"SATISFIABLE": "SAT", "SAT": "SAT", "UNSATISFIABLE": "UNSAT", "UNSAT": "UNSAT",
                   "UNKNOWN": "UNKNOWN", "INDETERMINATE": "UNKNOWN", "ERROR": "ERROR"}


# ----------------------------------------------------------------------------
# Solver-Ausgabe
# ----------------------------------------------------------------------------

def parse_solver_output(stdout: str, stderr: str, returncode: int) -> Tuple[str, Dict[int, bool], Optional[float]]:
    """Ermittelt (Status, Modell, solver-interne Zeit in ms) aus der Ausgabe.

    Reihenfolge: ``s``-Zeile (SAT-Competition) -> ``Status:``-Zeile (Subgraph-SAT-Solver)
    -> alleinstehende Ergebniszeile (MiniSat-Stil) -> Rückgabecode 10/20.
    Ein Lauf ohne erkennbares Ergebnis ist bei Rückgabecode 0 ``NO_OUTPUT``,
    sonst ``ERROR``. Ein Rückgabecode außerhalb von {0, 10, 20} ergibt immer ``ERROR``.

    Hinweis: Der Subgraph-SAT-Solver liefert Rückgabecode 20 auch bei UNKNOWN und
    bei Solver-Fehlern; deshalb hat die ``Status:``-Zeile Vorrang vor dem Code.
    """
    text = stdout + "\n" + stderr
    model = parse_model(stdout.splitlines())
    if not model:
        am = _RE_ASSIGN.search(stdout)
        if am:
            model = {int(v): f == "T" for v, f in _RE_ASSIGN_ITEM.findall(am.group(1))}

    internal = None
    m = _RE_TOTAL_TIME.search(text) or _RE_TIME.search(text)
    if m:
        value = float(m.group(1))
        unit = (m.group(2) or "ms").lower()
        internal = value * 1000.0 if unit.startswith("s") and unit != "ms" else value

    status = None
    for rx in (_RE_S_LINE, _RE_STATUS_LINE, _RE_BARE_LINE):
        hit = rx.search(stdout) or rx.search(stderr)
        if hit:
            status = _WORD_TO_STATUS[hit.group(1).upper()]
            break
    if status is None:
        status = "SAT" if returncode == 10 else "UNSAT" if returncode == 20 else None

    if status is None:
        status = "NO_OUTPUT" if returncode == 0 else "ERROR"
    elif returncode not in (0, 10, 20):
        status = "ERROR"
    if status != "SAT":
        model = {}
    return status, model, internal


# ----------------------------------------------------------------------------
# Einzelner Lauf
# ----------------------------------------------------------------------------

@dataclass
class RunOutcome:
    status: str
    runtime_ms: float
    returncode: Optional[int]
    peak_memory_mb: Optional[float]
    model: Dict[int, bool] = field(default_factory=dict)
    solver_time_ms: Optional[float] = None
    output_head: str = ""


class SolverRunner:
    """Startet einen DIMACS-Solver als Prozess und misst Zeit und Speicher.

    ``solver`` ist ein Pfad oder ein Kommando mit Argumenten
    (z. B. ``"python -m src.reference_solver"``).
    """

    def __init__(self, solver: Union[str, Sequence[str]] = "SubgraphSATSolver",
                 label: Optional[str] = None, timeout: float = 30.0):
        self.cmd: List[str] = shlex.split(solver, posix=(os.name != "nt")) \
            if isinstance(solver, str) else list(solver)
        self.label = label or self._default_label(self.cmd)
        self.timeout = timeout
        self.available = self._probe()

    @staticmethod
    def _default_label(cmd: List[str]) -> str:
        """Kurzname: Modulname bei ``python -m modul``, sonst Dateiname ohne Endung."""
        if "-m" in cmd and cmd.index("-m") + 1 < len(cmd):
            return cmd[cmd.index("-m") + 1].split(".")[-1]
        name = Path(cmd[0]).name
        if name.lower().startswith("python") and len(cmd) > 1:
            name = Path(cmd[1]).name
        return Path(name).stem

    # -- Verfügbarkeit / Version
    def _probe(self) -> bool:
        try:
            subprocess.run(self.cmd + ["--version"], capture_output=True, timeout=10,
                           cwd=PROJECT_ROOT)
            return True
        except FileNotFoundError:
            print(f"Warning: Solver nicht gefunden: {' '.join(self.cmd)}")
            return False
        except subprocess.TimeoutExpired:
            return True
        except OSError as exc:
            print(f"Warning: Solver nicht startbar: {exc}")
            return False

    def version(self) -> Optional[str]:
        for flag in ("--version", "-v", "--help"):
            try:
                r = subprocess.run(self.cmd + [flag], capture_output=True, text=True,
                                   timeout=10, cwd=PROJECT_ROOT)
            except (OSError, subprocess.TimeoutExpired):
                return None
            line = (r.stdout or r.stderr).strip().splitlines()
            if r.returncode == 0 and line:
                return line[0][:200]
        return None

    # -- Lauf
    def run(self, cnf_path: Union[str, Path], timeout: Optional[float] = None) -> RunOutcome:
        timeout = self.timeout if timeout is None else timeout
        out, err = tempfile.TemporaryFile(), tempfile.TemporaryFile()
        timed_out = threading.Event()
        peak_mb: Optional[float] = None
        try:
            t0 = time.perf_counter_ns()
            try:
                proc = subprocess.Popen(self.cmd + [str(cnf_path)], stdout=out, stderr=err,
                                        cwd=PROJECT_ROOT)
            except OSError as exc:
                return RunOutcome("ERROR", 0.0, None, None, output_head=f"ERROR: {exc}")

            def _kill():
                timed_out.set()
                proc.kill()

            timer = threading.Timer(timeout, _kill)
            timer.start()
            if hasattr(os, "wait4"):
                _, wstatus, ru = os.wait4(proc.pid, 0)
                t1 = time.perf_counter_ns()
                rc = os.waitstatus_to_exitcode(wstatus)
                proc.returncode = rc
                scale = 1.0 / (1024 * 1024) if sys.platform == "darwin" else 1.0 / 1024
                peak_mb = ru.ru_maxrss * scale
            else:                                    # Windows: keine Rusage verfügbar
                rc = proc.wait()
                t1 = time.perf_counter_ns()
            timer.cancel()
            runtime_ms = (t1 - t0) / 1e6
            if timed_out.is_set():
                return RunOutcome("TIMEOUT", runtime_ms, rc, peak_mb)
            out.seek(0)
            err.seek(0)
            stdout = out.read().decode("utf-8", "replace")
            stderr = err.read().decode("utf-8", "replace")
            status, model, internal = parse_solver_output(stdout, stderr, rc)
            head = "\n".join(l for l in (stdout + stderr).splitlines()
                             if l and not l.startswith("v"))[:200]
            return RunOutcome(status, runtime_ms, rc, peak_mb, model, internal, head)
        finally:
            out.close()
            err.close()

    # -- Basislinie
    def calibrate(self, repetitions: int = 30) -> Dict[str, float]:
        """Misst die Prozessstart-Grundlast mit einer trivialen Instanz."""
        with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False) as f:
            f.write(TRIVIAL_CNF)
            path = f.name
        try:
            times = []
            for _ in range(max(3, repetitions)):
                o = self.run(path, timeout=10.0)
                if o.status in ("SAT", "UNSAT", "NO_OUTPUT"):
                    times.append(o.runtime_ms)
        finally:
            os.unlink(path)
        if not times:
            return {"n": 0, "median_ms": float("nan"), "mean_ms": float("nan"),
                    "std_ms": float("nan"), "min_ms": float("nan"), "max_ms": float("nan")}
        return {"n": len(times), "median_ms": statistics.median(times),
                "mean_ms": statistics.mean(times),
                "std_ms": statistics.stdev(times) if len(times) > 1 else 0.0,
                "min_ms": min(times), "max_ms": max(times)}


# ----------------------------------------------------------------------------
# Umgebung
# ----------------------------------------------------------------------------

def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unbekannt"


def _git_commit() -> Optional[str]:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                           text=True, timeout=5, cwd=PROJECT_ROOT)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def capture_environment(runner: Optional[SolverRunner] = None) -> Dict:
    """Betriebssystem, Hardware, Python-/Bibliotheksversionen, Timer, Solver."""
    try:
        import psutil
        mem_gb = round(psutil.virtual_memory().total / 2**30, 2)
    except ImportError:
        mem_gb = None
    clock = time.get_clock_info("perf_counter")
    env = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu_model": _cpu_model(),
        "cpu_count": os.cpu_count(),
        "memory_gb": mem_gb,
        "python": f"{platform.python_implementation()} {platform.python_version()}",
        "numpy": np.__version__,
        "timer": {"function": "time.perf_counter_ns", "implementation": clock.implementation,
                  "resolution_s": clock.resolution, "monotonic": clock.monotonic},
        "git_commit": _git_commit(),
    }
    if runner is not None:
        env["solver"] = {"label": runner.label, "command": runner.cmd,
                         "version": runner.version()}
    return env


# ----------------------------------------------------------------------------
# Statistik
# ----------------------------------------------------------------------------

def bootstrap_ci(values: Sequence[float], stat=np.median, n_boot: int = 2000,
                 alpha: float = 0.05, seed: int = 0) -> Tuple[float, float]:
    """Perzentil-Bootstrap-Konfidenzintervall (Standard: Median, 95 %)."""
    x = np.asarray(values, dtype=float)
    if len(x) < 2:
        return (float(x[0]), float(x[0])) if len(x) else (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    boots = stat(x[idx], axis=1)
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def describe(values: Sequence[float]) -> Dict[str, float]:
    """Kennzahlen einer Messreihe: n, Median, Quartile, Mittelwert, s, Min, Max, CI."""
    x = np.asarray(values, dtype=float)
    if len(x) == 0:
        return {}
    lo, hi = bootstrap_ci(x)
    return {
        "n": int(len(x)),
        "median_ms": float(np.median(x)),
        "q1_ms": float(np.percentile(x, 25)),
        "q3_ms": float(np.percentile(x, 75)),
        "mean_ms": float(x.mean()),
        "std_ms": float(x.std(ddof=1)) if len(x) > 1 else 0.0,
        "min_ms": float(x.min()),
        "max_ms": float(x.max()),
        "median_ci_lo_ms": lo,
        "median_ci_hi_ms": hi,
    }


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
