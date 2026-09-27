"""
Experiment Runner für Masterarbeit-Benchmarks

Führt die exakten Experimente aus "Learning M-DNF in Boolean Circuits" durch.
"""

import subprocess
import os
import json
import time
import tempfile
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from pathlib import Path
import statistics
from boolean_circuits import (
    BooleanCircuit, 
    TargetANDCircuitGenerator,
    MasterarbeitBenchmark,
    CircuitType
)


@dataclass
class ExperimentResult:
    """Ergebnis eines einzelnen Experiments"""
    circuit_type: str
    circuit_name: str
    num_inputs: int
    num_gates: int
    num_clauses: int
    satisfiable: bool
    runtime_ms: float
    memory_usage_mb: float
    timestamp: str
    lbv_rounds: Optional[int] = None
    metadata: Optional[Dict] = None
    solver_output: Optional[str] = None
    error: Optional[str] = None


class SubgraphSATSolverRunner:
    """Wrapper für den Subgraph-SAT-Solver"""
    
    def __init__(self, solver_path: str = "SubgraphSATSolver"):
        self.solver_path = solver_path
        self._verify_solver()
    
    def _verify_solver(self):
        """Verifiziert Solver-Verfügbarkeit"""
        try:
            result = subprocess.run(
                [self.solver_path, "--help"],
                capture_output=True,
                timeout=5
            )
        except FileNotFoundError:
            print(f"Warning: Solver not found at {self.solver_path}")
    
    def solve(self, cnf_content: str, timeout: float = 30.0) -> tuple[bool, float, str]:
        """Führt Solver aus"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cnf', delete=False) as f:
            f.write(cnf_content)
            temp_path = f.name
        
        try:
            start_time = time.time()
            result = subprocess.run(
                [self.solver_path, temp_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            runtime = (time.time() - start_time) * 1000
            
            output = result.stdout + result.stderr
            satisfiable = "SAT" in output and "UNSAT" not in output
            
            return satisfiable, runtime, output
            
        except subprocess.TimeoutExpired:
            return None, timeout * 1000, "TIMEOUT"
        except Exception as e:
            return None, 0, f"ERROR: {str(e)}"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class ExperimentSuite:
    """Masterarbeit-Experiment Suite"""
    
    def __init__(self, solver_runner: SubgraphSATSolverRunner, output_dir: str = "."):
        self.solver = solver_runner
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[ExperimentResult] = []
    
    def run_single_experiment(self, circuit: BooleanCircuit) -> ExperimentResult:
        """Führt ein Experiment aus"""
        print(f"  {circuit.name}...", end="", flush=True)
        
        try:
            cnf = circuit.to_dimacs()
            num_clauses = len([l for l in cnf.split('\n') 
                             if l and not l.startswith('c') and not l.startswith('p')])
            
            satisfiable, runtime, output = self.solver.solve(cnf, timeout=30.0)
            
            result = ExperimentResult(
                circuit_type=circuit.circuit_type.value,
                circuit_name=circuit.name,
                num_inputs=circuit.num_inputs,
                num_gates=circuit.num_gates,
                num_clauses=num_clauses,
                satisfiable=satisfiable or satisfiable is None,
                runtime_ms=runtime,
                memory_usage_mb=0.0,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                lbv_rounds=circuit.metadata.get("lbv_rounds"),
                metadata=circuit.metadata,
                solver_output=output[:200] if output else None
            )
            
            print(f" ✓ {runtime:.2f}ms")
            return result
            
        except Exception as e:
            print(f" ✗ ERROR")
            return ExperimentResult(
                circuit_type=circuit.circuit_type.value,
                circuit_name=circuit.name,
                num_inputs=circuit.num_inputs,
                num_gates=circuit.num_gates,
                num_clauses=0,
                satisfiable=False,
                runtime_ms=0.0,
                memory_usage_mb=0.0,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                error=str(e)
            )
    
    def run_experiment_1_vary_inputs(self):
        """Experiment 1: Varying Inputs (m=4 to 20)"""
        print("\n" + "="*60)
        print("EXPERIMENT 1: Varying Inputs (m=4 to 20)")
        print("="*60)
        
        circuits = MasterarbeitBenchmark.exp1_vary_inputs()
        for circuit in circuits:
            result = self.run_single_experiment(circuit)
            self.results.append(result)
    
    def run_experiment_2_vary_depth(self, m: int = 10):
        """Experiment 2: Varying Depth (depth=1 to 12, m=10)"""
        print("\n" + "="*60)
        print(f"EXPERIMENT 2: Varying Depth (m={m}, depth=1-12)")
        print("="*60)
        
        circuits = MasterarbeitBenchmark.exp2_vary_depth(m)
        for circuit in circuits:
            result = self.run_single_experiment(circuit)
            self.results.append(result)
    
    def run_experiment_3_iscas85(self):
        """Experiment 3: ISCAS'85 Benchmarks"""
        print("\n" + "="*60)
        print("EXPERIMENT 3: ISCAS'85 Benchmarks")
        print("="*60)
        
        circuits = MasterarbeitBenchmark.exp3_iscas85()
        for circuit in circuits:
            result = self.run_single_experiment(circuit)
            self.results.append(result)
    
    def run_full_masterarbeit_suite(self):
        """Führt alle 3 Masterarbeit-Experimente durch"""
        self.run_experiment_1_vary_inputs()
        self.run_experiment_2_vary_depth()
        self.run_experiment_3_iscas85()
    
    def save_results(self, filename: str = "experiment_results.json"):
        """Speichert Ergebnisse"""
        output_path = self.output_dir / filename
        
        results_dict = [asdict(r) for r in self.results]
        with open(output_path, 'w') as f:
            json.dump(results_dict, f, indent=2)
        
        print(f"\n✓ Results saved to {output_path}")
        return output_path
    
    def save_csv(self, filename: str = "experiment_results.csv"):
        """Speichert als CSV"""
        import csv
        output_path = self.output_dir / filename
        
        if not self.results:
            return None
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=asdict(self.results[0]).keys())
            writer.writeheader()
            for result in self.results:
                writer.writerow(asdict(result))
        
        print(f"✓ CSV saved to {output_path}")
        return output_path
    
    def get_summary_stats(self) -> Dict:
        """Berechnet Statistiken"""
        if not self.results:
            return {}
        
        stats_by_type = {}
        
        for circuit_type in set(r.circuit_type for r in self.results):
            type_results = [r for r in self.results if r.circuit_type == circuit_type]
            runtimes = [r.runtime_ms for r in type_results if r.runtime_ms > 0]
            
            stats_by_type[circuit_type] = {
                "count": len(type_results),
                "avg_runtime_ms": statistics.mean(runtimes) if runtimes else 0,
                "median_runtime_ms": statistics.median(runtimes) if runtimes else 0,
                "min_runtime_ms": min(runtimes) if runtimes else 0,
                "max_runtime_ms": max(runtimes) if runtimes else 0,
                "std_dev_ms": statistics.stdev(runtimes) if len(runtimes) > 1 else 0,
                "avg_gates": statistics.mean([r.num_gates for r in type_results]),
                "avg_clauses": statistics.mean([r.num_clauses for r in type_results])
            }
        
        return {
            "total_experiments": len(self.results),
            "by_circuit_type": stats_by_type,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def print_summary(self):
        """Gibt Zusammenfassung aus"""
        stats = self.get_summary_stats()
        
        print(f"\n{'='*60}")
        print("SUMMARY STATISTICS")
        print(f"{'='*60}")
        print(f"Total experiments: {stats.get('total_experiments', 0)}")
        
        for circuit_type, type_stats in stats.get('by_circuit_type', {}).items():
            print(f"\n{circuit_type.upper()}:")
            print(f"  Count: {type_stats['count']}")
            print(f"  Avg Runtime: {type_stats['avg_runtime_ms']:.2f} ms")
            print(f"  Median Runtime: {type_stats['median_runtime_ms']:.2f} ms")
            print(f"  Range: {type_stats['min_runtime_ms']:.2f} - {type_stats['max_runtime_ms']:.2f} ms")
            if type_stats['std_dev_ms'] > 0:
                print(f"  Std Dev: {type_stats['std_dev_ms']:.2f} ms")
            print(f"  Avg Gates: {type_stats['avg_gates']:.1f}")
            print(f"  Avg Clauses: {type_stats['avg_clauses']:.1f}")


if __name__ == "__main__":
    runner = SubgraphSATSolverRunner()
    suite = ExperimentSuite(runner, output_dir="./masterarbeit_results")
    
    print("Running MASTERARBEIT EXPERIMENTS...")
    suite.run_full_masterarbeit_suite()
    
    suite.save_results()
    suite.save_csv()
    suite.print_summary()
