#!/usr/bin/env python3
"""
Hauptskript für Subgraph-SAT-Solver Boolean Circuit Experimente

Führt vollständige Experiment-Suite durch und erstellt Visualisierungen
"""

import sys
import argparse
from pathlib import Path
from experiment_runner import SubgraphSATSolverRunner, ExperimentSuite, CircuitType
from visualizer import ExperimentVisualizer


def main():
    parser = argparse.ArgumentParser(
        description="Subgraph-SAT-Solver Boolean Circuit Experiment Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Führe Scaling-Experimente durch
  python3 run_experiments.py --scaling-experiment sequential --max-size 100

  # Führe Benchmark-Suite durch
  python3 run_experiments.py --benchmark-suite --base-size 10 --repeats 3

  # Visualisiere existierende Ergebnisse
  python3 run_experiments.py --visualize ./experiment_results/experiment_results.json

  # Alles durchführen
  python3 run_experiments.py --full-suite
        """
    )
    
    parser.add_argument('--solver-path', default='SubgraphSATSolver',
                       help='Pfad zum Subgraph-SAT-Solver Binary')
    parser.add_argument('--output-dir', default='./experiment_results',
                       help='Ausgabeverzeichnis für Ergebnisse')
    
    # Experiment-Optionen
    parser.add_argument('--scaling-experiment', 
                       choices=['sequential', 'parallel', 'grid', 'random'],
                       help='Führt Skalierungs-Experiment für gegebenen Typ durch')
    parser.add_argument('--benchmark-suite', action='store_true',
                       help='Führt vollständige Benchmark-Suite durch')
    parser.add_argument('--full-suite', action='store_true',
                       help='Führt vollständige Suite durch (Benchmark + Scaling)')
    
    # Parameter für Experimente
    parser.add_argument('--base-size', type=int, default=10,
                       help='Basis-Größe für Benchmarks')
    parser.add_argument('--max-size', type=int, default=100,
                       help='Maximale Größe für Skalierungs-Experimente')
    parser.add_argument('--step', type=int, default=10,
                       help='Schrittgröße für Skalierungs-Experimente')
    parser.add_argument('--repeats', type=int, default=3,
                       help='Wiederholungen für Benchmark-Tests')
    
    # Visualisierungs-Optionen
    parser.add_argument('--visualize', type=str, metavar='JSON_FILE',
                       help='Visualisiere Ergebnisse aus JSON-Datei')
    parser.add_argument('--formats', nargs='+', default=['svg', 'pdf'],
                       help='Export-Formate (svg, pdf, png)')
    parser.add_argument('--skip-visualization', action='store_true',
                       help='Überspringt Visualisierung nach Experimenten')
    
    args = parser.parse_args()
    
    # Wenn nur Visualisierung
    if args.visualize and not (args.scaling_experiment or args.benchmark_suite or args.full_suite):
        print(f"Loading results from {args.visualize}...")
        results = ExperimentVisualizer.load_results(args.visualize)
        
        output_dir = Path(args.visualize).parent / "plots"
        visualizer = ExperimentVisualizer(results, output_dir=str(output_dir))
        
        print("\nGenerating visualizations...")
        visualizer.export_all_plots(formats=args.formats)
        visualizer.create_summary_report()
        print("\n✓ Visualization complete!")
        return
    
    # Führe Experimente durch
    print("=" * 70)
    print("SUBGRAPH-SAT-SOLVER EXPERIMENT SUITE")
    print("=" * 70)
    
    runner = SubgraphSATSolverRunner(args.solver_path)
    suite = ExperimentSuite(runner, output_dir=args.output_dir)
    
    # Benchmark-Suite
    if args.benchmark_suite or args.full_suite:
        print("\n[1/2] Running Benchmark Suite...")
        suite.run_full_masterarbeit_suite()
        # suite.run_benchmark_suite(base_size=args.base_size, repeats=args.repeats)
    
    # Skalierungs-Experimente
    scaling_types = []
    if args.scaling_experiment:
        scaling_types = [CircuitType[args.scaling_experiment.upper()]]
    elif args.full_suite:
        scaling_types = [CircuitType.SEQUENTIAL, CircuitType.PARALLEL, 
                        CircuitType.GRID, CircuitType.RANDOM]
    
    if scaling_types:
        print("\n[2/2] Running Scaling Experiments...")
        for circuit_type in scaling_types:
            # suite.run_scaling_experiment(circuit_type, max_size=args.max_size, step=args.step)
            suite.run_experiment_1_vary_inputs()
            suite.run_experiment_2_vary_depth()
    
    # Speichere Ergebnisse
    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)
    
    results_json = suite.save_results()
    suite.save_csv()
    suite.print_summary()
    
    # Visualisierung
    if not args.skip_visualization:
        print("\n" + "=" * 70)
        print("GENERATING VISUALIZATIONS")
        print("=" * 70)
        
        output_dir = Path(args.output_dir)
        visualizer = ExperimentVisualizer(suite.results, output_dir=str(output_dir / "plots"))
        visualizer.export_all_plots(formats=args.formats)
        visualizer.create_summary_report()
    
    print("\n" + "=" * 70)
    print("✓ ALL EXPERIMENTS COMPLETE!")
    print("=" * 70)
    print(f"Results: {args.output_dir}")
    print(f"Plots: {Path(args.output_dir) / 'plots'}")


if __name__ == "__main__":
    main()
