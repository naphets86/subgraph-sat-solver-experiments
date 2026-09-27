#!/usr/bin/env python3
"""
Quick-Start Skript für Subgraph-SAT-Solver Experimente

Ermöglicht einfache Konfiguration und Durchführung von Experimenten
"""

import subprocess
import sys
from pathlib import Path


class QuickStart:
    """Interaktives Quick-Start Interface"""
    
    PRESETS = {
        'quick': {
            'name': 'Quick Test (2 min)',
            'args': [
                '--scaling-experiment', 'sequential',
                '--max-size', '30', '--step', '10',
                '--output-dir', './quick_results'
            ]
        },
        'standard': {
            'name': 'Standard Suite (10 min)',
            'args': [
                '--benchmark-suite',
                '--base-size', '10', '--repeats', '2',
                '--output-dir', './standard_results'
            ]
        },
        'full': {
            'name': 'Full Suite (30+ min)',
            'args': [
                '--full-suite',
                '--base-size', '10', '--max-size', '100', '--step', '15',
                '--repeats', '2',
                '--output-dir', './full_results'
            ]
        },
        'performance': {
            'name': 'Performance Analysis (20 min)',
            'args': [
                '--full-suite',
                '--base-size', '5', '--max-size', '150', '--step', '25',
                '--repeats', '3',
                '--output-dir', './performance_results'
            ]
        }
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
        
        print(f"  5. Custom configuration")
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
        args = [sys.executable, 'run_experiments.py'] + preset['args']
        
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
        subprocess.run(args)
    
    @staticmethod
    def run_custom(solver_path: str):
        """Interaktive Custom-Konfiguration"""
        print("\n" + "="*70)
        print("CUSTOM CONFIGURATION")
        print("="*70 + "\n")
        
        print("Experiment Type:")
        print("  1. Scaling (single circuit type)")
        print("  2. Benchmark Suite")
        print("  3. Full Suite (Benchmark + Scaling)")
        
        exp_type = input("\nSelect (1-3): ").strip()
        
        args = [sys.executable, 'run_experiments.py']
        
        if exp_type == '1':
            print("\nCircuit Type:")
            print("  1. Sequential")
            print("  2. Parallel")
            print("  3. Grid")
            print("  4. Random")
            
            circuit_choice = input("Select (1-4): ").strip()
            circuit_map = {'1': 'sequential', '2': 'parallel', '3': 'grid', '4': 'random'}
            
            if circuit_choice in circuit_map:
                circuit_type = circuit_map[circuit_choice]
                max_size = input("Max size (default 100): ").strip() or "100"
                step = input("Step (default 10): ").strip() or "10"
                
                args.extend([
                    '--scaling-experiment', circuit_type,
                    '--max-size', max_size,
                    '--step', step
                ])
        
        elif exp_type == '2':
            base_size = input("Base size (default 10): ").strip() or "10"
            repeats = input("Repeats (default 3): ").strip() or "3"
            
            args.extend([
                '--benchmark-suite',
                '--base-size', base_size,
                '--repeats', repeats
            ])
        
        elif exp_type == '3':
            base_size = input("Base size (default 10): ").strip() or "10"
            max_size = input("Max size (default 100): ").strip() or "100"
            step = input("Step (default 10): ").strip() or "10"
            repeats = input("Repeats (default 2): ").strip() or "2"
            
            args.extend([
                '--full-suite',
                '--base-size', base_size,
                '--max-size', max_size,
                '--step', step,
                '--repeats', repeats
            ])
        
        output_dir = input("\nOutput directory (default ./custom_results): ").strip() or "./custom_results"
        args.extend(['--output-dir', output_dir])
        
        if solver_path != "SubgraphSATSolver":
            args.extend(['--solver-path', solver_path])
        
        print(f"\n{'='*70}")
        print("Command:")
        print(f"  {' '.join(args)}\n")
        
        confirm = input("Start experiments? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("Cancelled.")
            return
        
        print("\n" + "-" * 70)
        subprocess.run(args)
    
    @staticmethod
    def visualize_results(solver_path: str):
        """Visualisierung von existierenden Ergebnissen"""
        print("\n" + "="*70)
        print("VISUALIZE RESULTS")
        print("="*70 + "\n")
        
        json_file = input("Path to experiment_results.json: ").strip()
        
        if not Path(json_file).exists():
            print(f"Error: {json_file} not found")
            return
        
        formats = input("Export formats (default 'svg pdf'): ").strip() or "svg pdf"
        format_list = formats.split()
        
        args = [
            sys.executable, 'run_experiments.py',
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
        subprocess.run(args)
    
    @staticmethod
    def main():
        """Hauptfunktion"""
        QuickStart.print_header()
        
        # Prüfe ob run_experiments.py existiert
        if not Path('run_experiments.py').exists():
            print("Error: run_experiments.py not found!")
            print("Please ensure you're in the correct directory.")
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
                QuickStart.run_preset('performance', solver_path)
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
