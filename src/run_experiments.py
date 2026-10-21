#!/usr/bin/env python3
"""
Hauptskript für die Subgraph-SAT-Solver-Experimente (verbesserter Messaufbau).

Führt die Experimente 1-3 (Target-AND, Target-AND-Random, ISCAS'85) sowie die in
der wissenschaftlichen Arbeit vorgeschlagenen Erweiterungen aus (Miter,
Skalierung bis 10^5 Gates, Vergleich mit weiteren Solvern) und erstellt
Visualisierungen.
"""

import argparse
import sys
from pathlib import Path

from src import resolve_output_dir
from src.experiment_runner import ExperimentSuite
from src.instances import PRESETS
from src.measurement import SolverRunner
from src.visualizer import ExperimentVisualizer

REFERENCE_SOLVER_CMD = [sys.executable, "-m", "src.reference_solver"]
DEFAULT_OUTPUT_PREFIX = "v2"       # src/results/v2/<preset>; die Daten der ersten Messreihe bleiben unberührt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Subgraph-SAT-Solver Boolean Circuit Experiment Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  # Funktionstest mit dem eingebauten Referenzsolver (ohne Subgraph-SAT-Solver)
  python -m src.run_experiments --preset quick --solver-path "" --with-reference

  # Standard-Preset mit Subgraph-SAT-Solver und MiniSat als Vergleich
  python -m src.run_experiments --preset standard --solver-path build/SubgraphSATSolver --with-solver minisat

  # Skalierung bis 10^5 Gates
  python -m src.run_experiments --preset scaling

  # Vorhandene Ergebnisse neu visualisieren
  python -m src.run_experiments --visualize src/results/v2/quick/experiment_results.json
        """,
    )
    parser.add_argument("--preset", choices=sorted(PRESETS), default=None,
                        help="Experiment-Preset (quick, standard, full, scaling)")
    parser.add_argument("--benchmark-suite", action="store_true",
                        help="Exp. 1-3 mit Standardparametern (wie --preset standard ohne Miter)")
    parser.add_argument("--full-suite", action="store_true",
                        help="Alias für --preset full")
    parser.add_argument("--solver-path", default="SubgraphSATSolver",
                        help="Hauptsolver: Pfad oder Kommando mit Argumenten; leer = keiner")
    parser.add_argument("--with-solver", action="append", default=[], metavar="CMD",
                        help="Zusätzlicher Vergleichssolver (mehrfach angebbar), z. B. minisat, cadical")
    parser.add_argument("--with-reference", action="store_true",
                        help="Eingebauten Python-CDCL-Referenzsolver als Vergleich hinzufügen")
    parser.add_argument("--output-dir", default=None,
                        help=f"Ausgabeverzeichnis (Standard: src/results/{DEFAULT_OUTPUT_PREFIX}/<preset>; "
                             "relative Pfade gelten relativ zu src/results)")
    # Überschreiben der Preset-Werte
    parser.add_argument("--repetitions", type=int, help="Wiederholungen je Instanz (überschreibt Preset)")
    parser.add_argument("--warmup", type=int, help="Warm-up-Läufe je Instanz (überschreibt Preset)")
    parser.add_argument("--timeout", type=float, help="Timeout je Lauf in Sekunden (überschreibt Preset)")
    # Visualisierung
    parser.add_argument("--visualize", type=str, metavar="JSON_FILE",
                        help="Visualisiere Ergebnisse aus JSON-Datei")
    parser.add_argument("--formats", nargs="+", default=["svg", "pdf"],
                        help="Export-Formate (svg, pdf, png)")
    parser.add_argument("--skip-visualization", action="store_true",
                        help="Überspringt Visualisierung nach Experimenten")
    return parser


def build_runners(args) -> list:
    """Erzeugt die SolverRunner; nicht startbare Solver werden gemeldet und übersprungen."""
    commands = []
    if args.solver_path.strip():
        commands.append(args.solver_path)
    commands.extend(args.with_solver)
    runners = [SolverRunner(cmd) for cmd in commands]
    if args.with_reference:
        runners.append(SolverRunner(REFERENCE_SOLVER_CMD, label="reference-cdcl"))
    labels = [r.label for r in runners]
    dupes = {l for l in labels if labels.count(l) > 1}
    if dupes:
        raise SystemExit(f"Solver-Labels nicht eindeutig: {sorted(dupes)}")
    return runners


def visualize_only(args) -> None:
    print(f"Loading results from {args.visualize}...")
    results = ExperimentVisualizer.load_results(args.visualize)
    output_dir = Path(args.visualize).parent / "plots"
    visualizer = ExperimentVisualizer(results, output_dir=str(output_dir))
    print("\nGenerating visualizations...")
    visualizer.export_all_plots(formats=args.formats)
    visualizer.create_summary_report()
    print("\n✓ Visualization complete!")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.visualize and not (args.preset or args.benchmark_suite or args.full_suite):
        visualize_only(args)
        return 0

    preset = args.preset or ("full" if args.full_suite else "standard")
    output_dir = resolve_output_dir(args.output_dir or f"{DEFAULT_OUTPUT_PREFIX}/{preset}")

    print("=" * 70)
    print("SUBGRAPH-SAT-SOLVER EXPERIMENT SUITE")
    print("=" * 70)

    runners = build_runners(args)
    if not any(r.available for r in runners):
        print("Fehler: kein Solver verfügbar. Mit --solver-path den Subgraph-SAT-Solver angeben "
              "oder --with-reference zum Testen des Messaufbaus verwenden.", file=sys.stderr)
        return 2

    suite = ExperimentSuite(runners, output_dir=output_dir)

    if args.benchmark_suite and not args.preset and not args.full_suite:
        # Nur Exp. 1-3 (ohne Miter/Skalierung); Parameter wie Preset "standard"
        p = PRESETS["standard"]
        suite.repetitions, suite.warmup = p.repetitions, p.warmup
        suite.timeout, suite.budget_s = p.timeout, p.budget_s
        suite.config = {"preset": "benchmark-suite", "repetitions": p.repetitions,
                        "warmup": p.warmup, "timeout_s": p.timeout, "budget_s": p.budget_s}
        suite.run_full_masterarbeit_suite()
    else:
        overrides = {k: v for k, v in (("repetitions", args.repetitions), ("warmup", args.warmup),
                                       ("timeout", args.timeout)) if v is not None}
        suite.run_preset(preset, **overrides)

    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)
    suite.save_all()
    suite.print_summary()

    if not args.skip_visualization:
        print("\n" + "=" * 70)
        print("GENERATING VISUALIZATIONS")
        print("=" * 70)
        visualizer = ExperimentVisualizer(suite.results, output_dir=str(output_dir / "plots"))
        visualizer.export_all_plots(formats=args.formats)
        visualizer.create_summary_report()

    wrong = [r for r in suite.results if r.correct is False
             or r.model_valid is False or r.circuit_valid is False]
    print("\n" + "=" * 70)
    print("✓ EXPERIMENTE ABGESCHLOSSEN" + (f" – {len(wrong)} Läufe mit unerwartetem Ergebnis!" if wrong else ""))
    print("=" * 70)
    print(f"Results: {output_dir}")
    print(f"Plots: {output_dir / 'plots'}")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
