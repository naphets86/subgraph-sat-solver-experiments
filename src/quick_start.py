#!/usr/bin/env python3
"""
Quick-Start Skript für Subgraph-SAT-Solver Experimente

Ermöglicht einfache Konfiguration und Durchführung von Experimenten
"""

import subprocess
import sys
from pathlib import Path

from src import SRC_DIR

PROJECT_ROOT = SRC_DIR.parent
RUN_MODULE = 'src.run_experiments'


class QuickStart:
    """Interaktives Quick-Start Interface"""

    PRESETS = {
        'quick': {'name': 'Quick (Funktionstest, 5 Wiederholungen)', 'args': ['--preset', 'quick']},
        'standard': {'name': 'Standard (Exp. 1-3 + Miter, 15 Wiederholungen)', 'args': ['--preset', 'standard']},
        'full': {'name': 'Full (Exp. 1-3, Miter, Skalierung, 30 Wiederholungen)', 'args': ['--preset', 'full']},
        'scaling': {'name': 'Skalierung bis 10^5 Gates', 'args': ['--preset', 'scaling']},
    }

    @staticmethod
    def print_header():
        """Gibt Willkommens-Text aus"""
        print("\n" + "=" * 70)
        print("SUBGRAPH-SAT-SOLVER EXPERIMENT FRAMEWORK")
        print("Boolean Circuit Performance Analysis")
        print("=" * 70 + "\n")
    
    @staticmethod
    def show_menu():
        """Zeigt Auswahlmenü"""
        print("Select experiment preset:\n")
        
        for i, (key, preset) in enumerate(QuickStart.PRESETS.items(), 1):
            print(f"  {i}. {preset['name']}")
        
        print(f"  5. Custom configuration (Wiederholungen, Timeout, Vergleichssolver)")
        print(f"  6. Visualize existing results")
        print(f"  0. Exit\n")
        
        return input("Enter choice (0-6): ").strip()
    
    @staticmethod
    def get_solver_path():
        """Fragt nach Pfad zum Solver"""
        print("\nSolver Configuration:")
        print("-" * 40)
        
        default_path = "SubgraphSATSolver"
        print(f"Default: {default_path}")
        
        user_input = input("Enter solver path (or press Enter for default): ").strip()
        
        if user_input:
            if not Path(user_input).exists():
                print(f"⚠ Warning: {user_input} not found")
                print("  (Solver will be called as-is, may fail if not in PATH)")
            return user_input
        
        return default_path
    
    @staticmethod
    def run_preset(key: str, solver_path: str):
        """Führt Preset-Experimente durch"""
        if key not in QuickStart.PRESETS:
            print("Invalid preset")
            return
        
        preset = QuickStart.PRESETS[key]
        args = [sys.executable, '-m', RUN_MODULE] + preset['args']
        
        if solver_path != "SubgraphSATSolver":
            args.extend(['--solver-path', solver_path])
        
        print(f"\n{'='*70}")
        print(f"Running: {preset['name']}")
        print(f"{'='*70}\n")
        
        print("Command:")
        print(f"  {' '.join(args)}\n")
        
        confirm = input("Start experiments? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("Cancelled.")
            return
        
        print("\n" + "-" * 70)
        subprocess.run(args, cwd=PROJECT_ROOT)
    
    @staticmethod
    def run_custom(solver_path: str):
        """Interaktive Custom-Konfiguration"""
        print("\n" + "="*70)
        print("CUSTOM CONFIGURATION")
        print("="*70 + "\n")

        names = list(QuickStart.PRESETS)
        for i, key in enumerate(names, 1):
            print(f"  {i}. {QuickStart.PRESETS[key]['name']}")
        choice = input(f"\nPreset (1-{len(names)}, default 2): ").strip() or "2"
        if not choice.isdigit() or not 1 <= int(choice) <= len(names):
            print("Invalid preset")
            return
        args = [sys.executable, '-m', RUN_MODULE, '--preset', names[int(choice) - 1]]

        repetitions = input("Wiederholungen (Enter = Preset-Wert): ").strip()
        if repetitions:
            args.extend(['--repetitions', repetitions])
        timeout = input("Timeout je Lauf in s (Enter = Preset-Wert): ").strip()
        if timeout:
            args.extend(['--timeout', timeout])
        if input("Eingebauten Referenzsolver zum Vergleich verwenden? (y/n): ").strip().lower() == 'y':
            args.append('--with-reference')
        extra = input("Weitere Vergleichssolver (Kommandos, mit Leerzeichen getrennt, z. B. 'minisat cadical'): ").split()
        for cmd in extra:
            args.extend(['--with-solver', cmd])

        output_dir = input("\nOutput directory (default src/results/v2/<preset>): ").strip()
        if output_dir:
            args.extend(['--output-dir', output_dir])

        if solver_path != "SubgraphSATSolver":
            args.extend(['--solver-path', solver_path])

        print(f"\n{'='*70}")
        print("Command:")
        print(f"  {' '.join(args)}\n")

        if input("Start experiments? (y/n): ").strip().lower() != 'y':
            print("Cancelled.")
            return

        print("\n" + "-" * 70)
        subprocess.run(args, cwd=PROJECT_ROOT)

    @staticmethod
    def visualize_results(solver_path: str):
        """Visualisierung von existierenden Ergebnissen"""
        print("\n" + "="*70)
        print("VISUALIZE RESULTS")
        print("="*70 + "\n")
        
        default_json = SRC_DIR / "results" / "v2" / "standard" / "experiment_results.json"
        json_file = input(f"Path to experiment_results.json (default {default_json.relative_to(PROJECT_ROOT)}): ").strip() or str(default_json)
        json_file = str(Path(json_file).resolve())
        
        if not Path(json_file).exists():
            print(f"Error: {json_file} not found")
            return
        
        formats = input("Export formats (default 'svg pdf'): ").strip() or "svg pdf"
        format_list = formats.split()
        
        args = [
            sys.executable, '-m', RUN_MODULE,
            '--visualize', json_file,
            '--formats'
        ] + format_list
        
        if solver_path != "SubgraphSATSolver":
            args.extend(['--solver-path', solver_path])
        
        print(f"\n{'='*70}")
        print("Command:")
        print(f"  {' '.join(args)}\n")
        
        confirm = input("Start visualization? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("Cancelled.")
            return
        
        print("\n" + "-" * 70)
        subprocess.run(args, cwd=PROJECT_ROOT)
    
    @staticmethod
    def main():
        """Hauptfunktion"""
        QuickStart.print_header()
        
        # Prüfe ob run_experiments.py existiert
        if not (SRC_DIR / 'run_experiments.py').exists():
            print("Error: src/run_experiments.py not found!")
            sys.exit(1)
        
        # Solver-Pfad
        solver_path = QuickStart.get_solver_path()
        
        # Hauptschleife
        while True:
            choice = QuickStart.show_menu()
            
            if choice == '0':
                print("Goodbye!")
                break
            elif choice == '1':
                QuickStart.run_preset('quick', solver_path)
            elif choice == '2':
                QuickStart.run_preset('standard', solver_path)
            elif choice == '3':
                QuickStart.run_preset('full', solver_path)
            elif choice == '4':
                QuickStart.run_preset('scaling', solver_path)
            elif choice == '5':
                QuickStart.run_custom(solver_path)
            elif choice == '6':
                QuickStart.visualize_results(solver_path)
            else:
                print("Invalid choice. Try again.\n")
            
            if choice in ['1', '2', '3', '4', '5', '6']:
                input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        QuickStart.main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(0)
