"""
Experiment Runner

Führt die Experimente aus "Learning M-DNF in Boolean Circuits" (Exp. 1-3) sowie
die in der wissenschaftlichen Arbeit vorgeschlagenen Erweiterungen (Miter,
Skalierung bis 10^5 Gates) mit dem verbesserten Messaufbau durch
(siehe ``src.measurement``).

Ergebnisdateien je Lauf-Verzeichnis:

    experiment_results.csv / .json   ein Eintrag je gemessenem Lauf
    summary.csv / .json              Kennzahlen je Instanz (Median, CI, ...)
    environment.json                 Betriebssystem, CPU, Python, Solver-Version
    baseline.json                    Prozessstart-Grundlast (triviale Instanz)
    config.json                      Preset, Wiederholungen, Timeout
"""

import csv
import os
import tempfile
import time
import statistics
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Sequence, Union

from src import RESULTS_DIR, resolve_output_dir
from src.cnf import check_model
from src.instances import Instance, PRESETS, build_instances
from src.measurement import (
    SolverRunner,
    capture_environment,
    describe,
    write_json,
)


@dataclass
class ExperimentResult:
    """Ergebnis eines einzelnen Solver-Laufs."""
    circuit_type: str
    circuit_name: str
    num_inputs: int
    num_gates: int
    num_clauses: int
    satisfiable: bool                      # status == "SAT"
    runtime_ms: float                      # Wallclock inkl. Prozessstart
    memory_usage_mb: float                 # Spitzen-RSS des Solver-Prozesses (NaN: unbekannt)
    timestamp: str
    lbv_rounds: Optional[int] = None
    metadata: Optional[Dict] = None
    solver_output: Optional[str] = None
    error: Optional[str] = None
    # --- neu im verbesserten Messaufbau
    solver_label: str = ""
    family: str = ""
    constraint: str = ""
    status: str = ""                       # SAT / UNSAT / TIMEOUT / ERROR / NO_OUTPUT
    expected: Optional[str] = None
    correct: Optional[bool] = None         # status == expected (falls bekannt)
    model_valid: Optional[bool] = None     # Modell erfüllt die CNF (Lauf 0 geprüft)
    circuit_valid: Optional[bool] = None   # Modell erfüllt den Circuit samt Ausgangsbedingung
    returncode: Optional[int] = None
    rep: int = 0
    runtime_net_ms: Optional[float] = None  # runtime_ms - Basislinie (>= 0)
    solver_time_ms: Optional[float] = None  # solver-interne Zeit, falls ausgegeben
    num_vars: Optional[int] = None


class ExperimentSuite:
    """Experiment-Suite mit Wiederholungen, Warm-up und Verifikation.

    ``solver_runner`` ist ein ``SolverRunner`` oder eine Liste davon (Vergleich
    mehrerer Solver auf denselben CNF-Dateien, z. B. Subgraph-SAT-Solver,
    MiniSat, CaDiCaL, Referenzsolver). Nicht verfügbare Solver werden übersprungen.
    """

    def __init__(self, solver_runner: Union[SolverRunner, Sequence[SolverRunner]], output_dir=None,
                 repetitions: int = 30, warmup: int = 3, timeout: float = 30.0,
                 budget_s: float = 60.0, min_repetitions: int = 3,
                 verbose: bool = True):
        runners = [solver_runner] if isinstance(solver_runner, SolverRunner) else list(solver_runner)
        if not runners:
            raise ValueError("Mindestens ein Solver erforderlich")
        self.solvers: List[SolverRunner] = runners
        self.solver = runners[0]                   # Rückwärtskompatibilität
        self.output_dir = resolve_output_dir(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.repetitions = repetitions
        self.warmup = warmup
        self.timeout = timeout
        self.budget_s = budget_s
        self.min_repetitions = min_repetitions
        self.verbose = verbose
        self.results: List[ExperimentResult] = []
        self.baselines: Dict[str, Dict[str, float]] = {}   # je Solver-Label
        self.config: Dict = {}

    @property
    def baseline(self) -> Dict[str, float]:
        """Basislinie des ersten Solvers (Rückwärtskompatibilität)."""
        return self.baselines.get(self.solver.label, {})

    @property
    def active_solvers(self) -> List[SolverRunner]:
        return [r for r in self.solvers if r.available]

    # ------------------------------------------------------------- Basislinie
    def calibrate(self) -> Dict[str, Dict[str, float]]:
        for runner in self.active_solvers:
            b = runner.calibrate(30)
            self.baselines[runner.label] = b
            if self.verbose:
                print(f"Basislinie {runner.label} (triviale Instanz, n={b['n']}): "
                      f"Median {b['median_ms']:.2f} ms, s={b['std_ms']:.2f} ms")
        return self.baselines

    def _baseline_ms(self, label: str) -> float:
        b = self.baselines.get(label, {}).get("median_ms")
        return 0.0 if b is None or b != b else float(b)

    # ----------------------------------------------------------- Einzelinstanz
    def measure_instance(self, inst: Instance, runner: Optional[SolverRunner] = None) -> List[ExperimentResult]:
        """Warm-up + Wiederholungen einer Instanz mit einem Solver; gibt alle Läufe zurück."""
        runner = runner or self.solver
        circuit = inst.circuit
        cnf = circuit.to_cnf(inst.constraint)
        with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False) as f:
            f.write(cnf.to_dimacs())
            path = f.name
        runs: List[ExperimentResult] = []
        try:
            first = None
            for _ in range(self.warmup):                 # Warm-up (verworfen)
                first = runner.run(path, self.timeout)
                if first.status in ("TIMEOUT", "ERROR", "NO_OUTPUT"):
                    break
            if first is None:
                reps = self.repetitions
            elif first.status == "TIMEOUT":              # Timeout schon im Warm-up
                reps = 1
            elif first.status in ("ERROR", "NO_OUTPUT"):  # Wiederholen bringt nichts
                reps = 1
            elif first.runtime_ms > 0:
                reps = int(self.budget_s * 1000.0 / first.runtime_ms)
                reps = max(self.min_repetitions, min(self.repetitions, reps))
            else:
                reps = self.repetitions
            model_valid: Optional[bool] = None
            circuit_valid: Optional[bool] = None
            base = self._baseline_ms(runner.label)
            for rep in range(reps):
                o = runner.run(path, self.timeout)
                if rep == 0 and o.status == "SAT" and o.model:
                    model_valid = check_model(cnf.clauses, o.model)
                    circuit_valid = circuit.check_model(o.model, inst.constraint)
                if inst.expected is None or o.status in ("TIMEOUT", "UNKNOWN"):
                    correct = None                       # kein Urteil möglich
                else:
                    correct = (o.status == inst.expected)
                runs.append(ExperimentResult(
                    circuit_type=circuit.circuit_type.value,
                    circuit_name=circuit.name,
                    num_inputs=circuit.num_inputs,
                    num_gates=circuit.num_gates,
                    num_clauses=cnf.num_clauses,
                    satisfiable=(o.status == "SAT"),
                    runtime_ms=o.runtime_ms,
                    memory_usage_mb=o.peak_memory_mb if o.peak_memory_mb is not None else float("nan"),
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                    lbv_rounds=circuit.metadata.get("lbv_rounds"),
                    metadata=circuit.metadata,
                    solver_output=o.output_head or None,
                    error=o.output_head if o.status == "ERROR" else None,
                    solver_label=runner.label,
                    family=inst.family,
                    constraint=inst.constraint,
                    status=o.status,
                    expected=inst.expected,
                    correct=correct,
                    returncode=o.returncode,
                    rep=rep,
                    runtime_net_ms=max(0.0, o.runtime_ms - base),
                    solver_time_ms=o.solver_time_ms,
                    num_vars=cnf.num_vars,
                ))
                if o.status == "TIMEOUT":
                    break
            for r in runs:                               # Modellprüfung gilt je Instanz
                r.model_valid = model_valid
                r.circuit_valid = circuit_valid
        finally:
            os.unlink(path)
        return runs

    def run_instance(self, inst: Instance) -> None:
        for runner in self.active_solvers:
            if self.verbose:
                print(f"  [{runner.label}] {inst.name} ({inst.circuit.num_gates} Gates)...",
                      end="", flush=True)
            runs = self.measure_instance(inst, runner)
            self.results.extend(runs)
            if self.verbose:
                statuses = sorted({r.status for r in runs})
                valid = [r.runtime_ms for r in runs if r.status != "TIMEOUT"] or [r.runtime_ms for r in runs]
                d = describe(valid)
                flag = ""
                if any(r.correct is False for r in runs):
                    flag = " ✗ UNERWARTETES ERGEBNIS"
                if any(r.model_valid is False or r.circuit_valid is False for r in runs):
                    flag += " ✗ MODELL UNGÜLTIG"
                print(f" {'/'.join(statuses)} n={len(runs)} Median {d['median_ms']:.2f} ms{flag}")

    # ---------------------------------------------------------------- Presets
    def run_preset(self, preset: str, **overrides) -> None:
        """Führt ein Preset aus. ``overrides``: repetitions, warmup, timeout, budget_s."""
        import dataclasses
        p = dataclasses.replace(PRESETS[preset], **overrides)
        self.repetitions, self.warmup = p.repetitions, p.warmup
        self.timeout, self.budget_s = p.timeout, p.budget_s
        self.config = {"preset": preset, "repetitions": p.repetitions, "warmup": p.warmup,
                       "timeout_s": p.timeout, "budget_s": p.budget_s,
                       "min_repetitions": self.min_repetitions,
                       "description": p.description}
        print("\n" + "=" * 60)
        print(f"PRESET {preset}: {p.description}")
        print("=" * 60)
        self.calibrate()
        if not self.active_solvers:
            raise RuntimeError("Kein Solver verfügbar")
        for inst in build_instances(preset):
            self.run_instance(inst)

    # ----------------------------------------------- Kompatibilität (Exp. 1-3)
    def run_experiment_1_vary_inputs(self):
        from src.instances import exp1
        for inst in exp1():
            self.run_instance(inst)

    def run_experiment_2_vary_depth(self, m: int = 10):
        from src.instances import exp2
        for inst in exp2(m):
            self.run_instance(inst)

    def run_experiment_3_iscas85(self):
        from src.instances import exp3
        for inst in exp3():
            self.run_instance(inst)

    def run_full_masterarbeit_suite(self):
        if not self.baselines:
            self.calibrate()
        self.run_experiment_1_vary_inputs()
        self.run_experiment_2_vary_depth()
        self.run_experiment_3_iscas85()

    # ------------------------------------------------------------ Speichern
    def save_results(self, filename: str = "experiment_results.json"):
        output_path = self.output_dir / filename
        write_json(output_path, [asdict(r) for r in self.results])
        print(f"\n✓ Results saved to {output_path}")
        return output_path

    def save_csv(self, filename: str = "experiment_results.csv"):
        output_path = self.output_dir / filename
        if not self.results:
            return None
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(self.results[0]).keys()))
            writer.writeheader()
            for r in self.results:
                writer.writerow(asdict(r))
        print(f"✓ CSV saved to {output_path}")
        return output_path

    def summary_rows(self) -> List[Dict]:
        """Kennzahlen je (Solver, Instanz); Zeitstatistik ohne Timeout-Läufe."""
        rows = []
        keys = list(dict.fromkeys((r.solver_label, r.circuit_name) for r in self.results))
        verdicts = self.cross_check()
        for label, name in keys:
            runs = [r for r in self.results if r.solver_label == label and r.circuit_name == name]
            r0 = runs[0]
            valid = [r for r in runs if r.status != "TIMEOUT"]
            d = describe([r.runtime_ms for r in valid]) if valid else {}
            nets = [r.runtime_net_ms for r in valid if r.runtime_net_ms is not None]
            mem = [r.memory_usage_mb for r in valid if r.memory_usage_mb == r.memory_usage_mb]
            statuses = sorted({r.status for r in runs})
            judged = [r.correct for r in runs if r.correct is not None]
            rows.append({
                "solver_label": label, "family": r0.family, "circuit_name": name,
                "num_inputs": r0.num_inputs, "num_gates": r0.num_gates,
                "num_clauses": r0.num_clauses, "num_vars": r0.num_vars,
                "constraint": r0.constraint,
                "expected": r0.expected, "statuses": "/".join(statuses),
                "status_consistent": len(statuses) == 1,
                "timeouts": len(runs) - len(valid),
                "correct": all(judged) if judged else None,
                "model_valid": r0.model_valid,
                "circuit_valid": r0.circuit_valid,
                "solvers_agree": verdicts.get(name),
                "median_net_ms": float(statistics.median(nets)) if nets else None,
                "peak_memory_mb_max": max(mem) if mem else None,
                **d,
            })
        return rows

    def cross_check(self) -> Dict[str, Optional[bool]]:
        """Je Instanz: liefern alle Solver mit eindeutigem Ergebnis dasselbe?
        ``None``, wenn weniger als zwei Solver ein SAT/UNSAT-Ergebnis haben."""
        verdict: Dict[str, Dict[str, set]] = {}
        for r in self.results:
            if r.status in ("SAT", "UNSAT"):
                verdict.setdefault(r.circuit_name, {}).setdefault(r.solver_label, set()).add(r.status)
        out: Dict[str, Optional[bool]] = {}
        for name, per_solver in verdict.items():
            if len(per_solver) < 2:
                out[name] = None
                continue
            allv = set().union(*per_solver.values())
            out[name] = len(allv) == 1
        return out

    def save_summary(self):
        rows = self.summary_rows()
        if not rows:
            return
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(self.output_dir / "summary.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        write_json(self.output_dir / "summary.json", rows)

    def save_metadata(self):
        env = capture_environment(self.active_solvers[0] if self.active_solvers else None)
        env["solvers"] = [{"label": r.label, "command": r.cmd, "available": r.available,
                           "version": r.version() if r.available else None} for r in self.solvers]
        write_json(self.output_dir / "environment.json", env)
        write_json(self.output_dir / "baseline.json", self.baselines)
        write_json(self.output_dir / "config.json", self.config)

    def save_all(self):
        self.save_results()
        self.save_csv()
        self.save_summary()
        self.save_metadata()

    # --------------------------------------------------------------- Ausgabe
    def get_summary_stats(self) -> Dict:
        stats_by_type: Dict[str, Dict] = {}
        multi = len({r.solver_label for r in self.results}) > 1
        groups = sorted({(r.solver_label, r.family or r.circuit_type) for r in self.results})
        for label, family in groups:
            rs = [r for r in self.results if (r.solver_label, r.family or r.circuit_type) == (label, family)
                  and r.status not in ("TIMEOUT", "ERROR", "NO_OUTPUT")]
            if not rs:
                continue
            d = describe([r.runtime_ms for r in rs])
            stats_by_type[f"{label}:{family}" if multi else family] = {
                "count": len(rs),
                "avg_runtime_ms": d["mean_ms"], "median_runtime_ms": d["median_ms"],
                "min_runtime_ms": d["min_ms"], "max_runtime_ms": d["max_ms"],
                "std_dev_ms": d["std_ms"],
                "avg_gates": sum(r.num_gates for r in rs) / len(rs),
                "avg_clauses": sum(r.num_clauses for r in rs) / len(rs),
            }
        return {"total_experiments": len(self.results), "by_circuit_type": stats_by_type,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}

    def print_summary(self):
        stats = self.get_summary_stats()
        print(f"\n{'=' * 60}\nSUMMARY STATISTICS\n{'=' * 60}")
        print(f"Total runs: {stats['total_experiments']}")
        by_status: Dict[str, int] = {}
        for r in self.results:
            by_status[r.status] = by_status.get(r.status, 0) + 1
        print("Status: " + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
        wrong = [r for r in self.results if r.correct is False]
        print(f"Unerwartete Ergebnisse: {len(wrong)}")
        bad_models = [r for r in self.results if r.rep == 0 and (r.model_valid is False or r.circuit_valid is False)]
        print(f"Ungültige Modelle: {len(bad_models)}")
        disagree = [n for n, ok in self.cross_check().items() if ok is False]
        if len(self.solvers) > 1:
            print(f"Instanzen mit widersprüchlichen Solver-Ergebnissen: {len(disagree)}"
                  + (f" ({', '.join(disagree[:5])})" if disagree else ""))
        for family, s in stats["by_circuit_type"].items():
            print(f"\n{family.upper()}:")
            print(f"  Runs: {s['count']}")
            print(f"  Median: {s['median_runtime_ms']:.2f} ms  Mean: {s['avg_runtime_ms']:.2f} ms")
            print(f"  Range: {s['min_runtime_ms']:.2f} - {s['max_runtime_ms']:.2f} ms")
            print(f"  Avg Gates: {s['avg_gates']:.1f}  Avg Clauses: {s['avg_clauses']:.1f}")


# Rückwärtskompatibler Name
SubgraphSATSolverRunner = SolverRunner


if __name__ == "__main__":
    runner = SolverRunner("SubgraphSATSolver")
    suite = ExperimentSuite(runner, output_dir=RESULTS_DIR)
    suite.run_preset("standard")
    suite.save_all()
    suite.print_summary()
