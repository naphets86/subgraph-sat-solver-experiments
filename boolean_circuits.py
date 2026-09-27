"""
Boolean Circuit Generator für Subgraph-SAT-Solver Experimente

Generiert die EXAKTEN Boolean Circuits aus der Masterarbeit:
- Target-AND Circuits (LBV-Zielassignments) - Exp 1
- Target-AND mit Random Intermediate Layers - Exp 2
- ISCAS'85 Benchmarks - Exp 3
- Zusätzliche: Sequential, Parallel, Grid, Random

Basiert auf: Epp, S. (2013). "Learning M-DNF in Boolean Circuits"
"""

from typing import List, Tuple, Set, Dict, Optional
from pathlib import Path
import random
import math
from dataclasses import dataclass
from enum import Enum


class CircuitType(Enum):
    """Typen von Boolean Circuits"""
    # Aus der Masterarbeit / LSAT-Paper
    TARGET_AND = "target_and"           # Target-AND Circuit (Exp 1)
    TARGET_AND_RANDOM = "target_and_random"  # Target-AND + Random Layers (Exp 2)
    ISCAS85 = "iscas85"                # ISCAS'85 Benchmarks (Exp 3)
    
    # Zusätzliche Standard-Typen
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    GRID = "grid"
    RANDOM = "random"


@dataclass
class BooleanCircuit:
    """Repräsentation eines Boolean Circuits"""
    gates: List[Tuple[str, List[int]]]  # [(gate_type, input_indices), ...]
    num_inputs: int
    num_outputs: int
    circuit_type: CircuitType
    size: int
    name: str = ""
    metadata: Dict = None  # Zusätzliche Informationen (z.B. depth, m, etc.)
    
    def __post_init__(self):
        self.num_gates = len(self.gates)
        if self.metadata is None:
            self.metadata = {}
    
    def to_dimacs(self) -> str:
        """Konvertiert Circuit zu DIMACS CNF Format"""
        clauses = []
        num_vars = self.num_inputs + self.num_gates + 1
        
        for gate_idx, (gate_type, inputs) in enumerate(self.gates):
            gate_var = self.num_inputs + gate_idx + 1
            input_vars = [i + 1 for i in inputs]
            
            # Tseitin-Transformation
            if gate_type == "AND":
                clauses.append([-gate_var] + input_vars)
                for inp in input_vars:
                    clauses.append([-gate_var, inp])
                clauses.append([gate_var] + [-i for i in input_vars])
                
            elif gate_type == "OR":
                clauses.append([gate_var] + [-i for i in input_vars])
                for inp in input_vars:
                    clauses.append([gate_var, -inp])
                clauses.append([-gate_var] + input_vars)
                
            elif gate_type == "NOT":
                clauses.append([-gate_var, -input_vars[0]])
                clauses.append([gate_var, input_vars[0]])
                
            elif gate_type == "XOR":
                a, b = input_vars[0], input_vars[1]
                clauses.append([gate_var, a, b])
                clauses.append([gate_var, -a, -b])
                clauses.append([-gate_var, a, -b])
                clauses.append([-gate_var, -a, b])
            
            elif gate_type == "NAND":
                clauses.append([gate_var] + [-i for i in input_vars])
                for inp in input_vars:
                    clauses.append([gate_var, -inp])
                clauses.append([-gate_var] + input_vars)
                
            elif gate_type == "NOR":
                clauses.append([-gate_var] + input_vars)
                for inp in input_vars:
                    clauses.append([-gate_var, inp])
                clauses.append([gate_var] + [-i for i in input_vars])
        
        num_clauses = len(clauses)
        dimacs = f"c Circuit: {self.name or self.circuit_type.value}\n"
        dimacs += f"c Type: {self.circuit_type.value}\n"
        if self.metadata:
            for key, value in self.metadata.items():
                dimacs += f"c {key}: {value}\n"
        dimacs += f"p cnf {num_vars} {num_clauses}\n"
        
        for clause in clauses:
            dimacs += " ".join(map(str, clause)) + " 0\n"
        
        return dimacs


# ============================================================================
# MASTERARBEIT: Target-AND Circuits
# ============================================================================

class TargetANDCircuitGenerator:
    """
    Generiert Target-AND Circuits wie in der Masterarbeit.
    
    Diese Circuits werden befriedigt durch GENAU EINE Zuweisung:
    Die Zuweisung, die LBV (Logarithmic Binary Search) in der letzten
    Runde findet.
    
    Struktur:
        - Inputs: x_0, x_1, ..., x_{m-1}
        - NOT gates für alle Inputs
        - Target AND: AND über alle Literale, die der Zuweisung entsprechen
        - Output: Das Target AND
    """
    
    @staticmethod
    def compute_lbv_last_assignment(m: int) -> Dict[int, bool]:
        """
        Berechnet die Zuweisung, die LBV in der letzten Runde findet.
        
        Simuliert den LBV-Halbierungsprozess:
        - Start: alle False (nach Round 1 / all-zeros)
        - Jede Runde: toggle erste flip_size Inputs
        - flip_size halbiert sich jede Runde
        
        Args:
            m: Anzahl der Eingaben (>= 2)
        
        Returns:
            Dict mapping input_index -> bool value
        """
        assignment = {i: False for i in range(m)}
        flip_size = m // 2
        
        while flip_size >= 1:
            for i in range(flip_size):
                assignment[i] = not assignment[i]
            flip_size //= 2
        
        return assignment
    
    @staticmethod
    def lbv_round_count(m: int) -> int:
        """
        Anzahl der Runden, die LBV durchführt.
        Alle Runden außer der letzten schlagen fehl.
        
        Returns:
            ⌊log₂(m)⌋ + 2
        """
        steps = 0
        flip_size = m // 2
        while flip_size >= 1:
            steps += 1
            flip_size //= 2
        return 2 + (steps - 1)
    
    @staticmethod
    def build_target_and_circuit(m: int) -> BooleanCircuit:
        """
        Erzeugt Target-AND Circuit für m Eingaben.
        
        Args:
            m: Anzahl der Eingaben (4 <= m <= 20 für Experimente)
        
        Returns:
            BooleanCircuit mit einzelnem Output "output"
        """
        if m < 2:
            raise ValueError("m must be >= 2")
        
        target = TargetANDCircuitGenerator.compute_lbv_last_assignment(m)
        gates = []
        
        # Input-Indizes: 0 bis m-1
        # NOT-gates: m bis 2m-1
        # AND-gates: ab 2m
        
        # NOT-gates für alle Inputs
        not_indices = {}
        for i in range(m):
            not_idx = m + i
            gates.append(("NOT", [i]))
            not_indices[i] = not_idx
        
        # Literale (entweder Input oder NOT Input)
        literal_indices = []
        for i in range(m):
            if target[i]:
                literal_indices.append(i)  # x_i
            else:
                literal_indices.append(not_indices[i])  # NOT x_i
        
        # Baumstruktur für AND
        current_indices = literal_indices
        while len(current_indices) > 1:
            next_indices = []
            for i in range(0, len(current_indices), 2):
                if i + 1 < len(current_indices):
                    and_idx = len(gates) + m  # Neue Gate-ID
                    gates.append(("AND", [current_indices[i], current_indices[i+1]]))
                    next_indices.append(len(gates) - 1 + m)
                else:
                    next_indices.append(current_indices[i])
            current_indices = next_indices
        
        output_idx = current_indices[0]
        
        # Adjustiere Gate-Indizes
        adjusted_gates = []
        gate_counter = m
        for gate_type, inputs in gates:
            # Mappt Input-Indizes
            adjusted_inputs = []
            for inp in inputs:
                if inp < m:
                    adjusted_inputs.append(inp)  # Input
                else:
                    # NOT oder AND gate
                    adjusted_inputs.append(inp)
            adjusted_gates.append((gate_type, adjusted_inputs))
            gate_counter += 1
        
        return BooleanCircuit(
            gates=adjusted_gates,
            num_inputs=m,
            num_outputs=1,
            circuit_type=CircuitType.TARGET_AND,
            size=len(adjusted_gates),
            name=f"TargetAND_m{m}",
            metadata={
                "m": m,
                "lbv_rounds": TargetANDCircuitGenerator.lbv_round_count(m),
                "satisfying_assignment": str(target)
            }
        )
    
    @staticmethod
    def build_target_and_with_random_layers(m: int, depth: int, seed: int = 0) -> BooleanCircuit:
        """
        Erzeugt Target-AND mit random intermediate layers.
        
        Struktur:
            - Inputs
            - `depth` Schichten mit zufälligen Gates
            - Target AND
            - Final AND kombiniert Target und Random Layers
        
        Args:
            m: Anzahl Eingaben (z.B. 10)
            depth: Anzahl random Schichten (1-12)
            seed: Random seed
        
        Returns:
            BooleanCircuit mit Metadata
        """
        if m < 2 or depth < 0:
            raise ValueError("m >= 2 and depth >= 0 required")
        
        # Nutze einfachere Implementierung für schnelle Tests
        gates = []
        
        # Inputs: 0 bis m-1
        # NOT gates: m bis 2m-1
        for i in range(m):
            gates.append(("NOT", [i]))
        
        # Target AND Construction
        target = TargetANDCircuitGenerator.compute_lbv_last_assignment(m)
        literal_indices = [i if target[i] else m + i for i in range(m)]
        
        # AND tree für target
        current_indices = literal_indices
        while len(current_indices) > 1:
            next_indices = []
            for i in range(0, len(current_indices), 2):
                if i + 1 < len(current_indices):
                    gates.append(("AND", [current_indices[i], current_indices[i+1]]))
                    next_indices.append(len(gates) - 1 + m)
                else:
                    next_indices.append(current_indices[i])
            current_indices = next_indices
        
        target_idx = current_indices[0]
        
        # Random intermediate layers
        rng = random.Random(seed)
        current_layer = list(range(m))
        gate_types = ["AND", "OR", "NAND", "NOR", "XOR"]
        
        for layer_num in range(depth):
            layer_size = max(2, len(current_layer) // 2 + rng.randint(0, 2))
            next_layer = []
            
            for _ in range(layer_size):
                gate_type = rng.choice(gate_types)
                fan_in = rng.randint(2, min(3, len(current_layer)))
                inputs = rng.sample(current_layer, min(fan_in, len(current_layer)))
                
                gates.append((gate_type, inputs))
                next_layer.append(len(gates) - 1 + m)
            
            current_layer = next_layer
        
        random_layer_idx = current_layer[0] if current_layer else target_idx
        
        # Final AND combining target and random layers
        if random_layer_idx != target_idx:
            gates.append(("AND", [target_idx, random_layer_idx]))
            output_idx = len(gates) - 1 + m
        else:
            output_idx = target_idx
        
        return BooleanCircuit(
            gates=gates,
            num_inputs=m,
            num_outputs=1,
            circuit_type=CircuitType.TARGET_AND_RANDOM,
            size=len(gates),
            name=f"TargetAND_m{m}_d{depth}",
            metadata={
                "m": m,
                "depth": depth,
                "lbv_rounds": TargetANDCircuitGenerator.lbv_round_count(m)
            }
        )


# ============================================================================
# Experiment Benchmarking Suite (aus der Masterarbeit)
# ============================================================================

class MasterarbeitBenchmark:
    """
    Standard-Benchmarks aus der Masterarbeit:
    
    Exp 1: Vary inputs (fixed depth=0)
    Exp 2: Vary depth (fixed m=10)
    Exp 3: ISCAS'85 Benchmarks -> Dynamisch aus dem Ordner geladen
    """
    
    @staticmethod
    def exp1_vary_inputs() -> List[BooleanCircuit]:
        """Experiment 1: Varying Inputs (m=4 to 20)"""
        circuits = []
        for m in range(4, 21, 2):
            circuit = TargetANDCircuitGenerator.build_target_and_circuit(m)
            circuits.append(circuit)
        return circuits
    
    @staticmethod
    def exp2_vary_depth(m: int = 10) -> List[BooleanCircuit]:
        """Experiment 2: Varying Depth (depth=1 to 12, m=10)"""
        circuits = []
        for depth in range(1, 13):
            circuit = TargetANDCircuitGenerator.build_target_and_with_random_layers(m, depth, seed=42)
            circuits.append(circuit)
        return circuits
    
    @staticmethod
    def load_bench_file(file_path: Path) -> BooleanCircuit:
        """Parst eine Standard-.bench-Datei in ein BooleanCircuit-Objekt"""
        gates = []
        inputs = []
        outputs = []
        wire_map: Dict[str, int] = {}
        
        def get_wire_id(name: str) -> int:
            name = name.strip()
            if name not in wire_map:
                wire_map[name] = len(wire_map)
            return wire_map[name]

        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                if line.upper().startswith("INPUT"):
                    name = line.split("(")[1].split(")")[0]
                    inputs.append(get_wire_id(name))
                    
                elif line.upper().startswith("OUTPUT"):
                    name = line.split("(")[1].split(")")[0]
                    outputs.append(get_wire_id(name))
                    
                elif "=" in line:
                    out_part, gate_part = line.split("=")
                    out_wire = get_wire_id(out_part)
                    
                    gate_type = gate_part.split("(")[0].strip().upper()
                    in_parts = gate_part.split("(")[1].split(")")[0].split(",")
                    in_wires = [get_wire_id(p) for p in in_parts if p.strip()]
                    
                    gates.append((gate_type, in_wires, out_wire))

        num_inputs = len(inputs)
        sorted_gates = [None] * len(gates)
        
        for g_type, g_ins, g_out in gates:
            gate_pos = g_out - num_inputs
            if 0 <= gate_pos < len(sorted_gates):
                adj_ins = [i for i in g_ins]
                sorted_gates[gate_pos] = (g_type, adj_ins)
        
        final_gates = [g for g in sorted_gates if g is not None]

        return BooleanCircuit(
            gates=final_gates,
            num_inputs=num_inputs,
            num_outputs=len(outputs),
            circuit_type=CircuitType.ISCAS85,
            size=len(final_gates),
            name=file_path.stem,
            metadata={"benchmark": "ISCAS'85", "original_file": file_path.name}
        )

    @staticmethod
    def exp3_iscas85() -> List[BooleanCircuit]:
        """Lädt automatisch alle .bench-Dateien aus dem ./iscas85/ Ordner"""
        circuits = []
        iscas_dir = Path(__file__).parent / "iscas85"
        
        if not iscas_dir.exists():
            iscas_dir = Path("iscas85")
            
        if not iscas_dir.exists():
            print(f"[Warning] Ordner {iscas_dir} nicht gefunden!")
            return circuits
            
        for bench_file in sorted(iscas_dir.glob("*.bench")):
            try:
                circuit = MasterarbeitBenchmark.load_bench_file(bench_file)
                circuits.append(circuit)
            except Exception as e:
                print(f"[Error] Konnte {bench_file.name} nicht parsen: {e}")
                
        return circuits


# ============================================================================
# Standard Circuit Generators (für zusätzliche Experimente)
# ============================================================================

class CircuitGenerator:
    """Generiert verschiedene Circuit-Typen"""
    
    @staticmethod
    def sequential(num_gates: int) -> BooleanCircuit:
        """Linear verkettete Gates"""
        gates = []
        gates.append(("AND", [0, 1]))
        for i in range(1, num_gates):
            gates.append(("OR", [i, min(i+1, 2)]))
        
        return BooleanCircuit(
            gates=gates,
            num_inputs=min(num_gates + 2, 3),
            num_outputs=1,
            circuit_type=CircuitType.SEQUENTIAL,
            size=num_gates,
            name=f"Sequential_{num_gates}"
        )
    
    @staticmethod
    def parallel(depth: int) -> BooleanCircuit:
        """Baumstruktur"""
        gates = []
        current_layer_size = 2
        
        for _ in range(depth):
            gates_in_layer = current_layer_size // 2
            for i in range(gates_in_layer):
                gates.append(("AND", [len(gates) + i, len(gates) + i + 1]))
            current_layer_size = gates_in_layer
        
        return BooleanCircuit(
            gates=gates,
            num_inputs=2,
            num_outputs=1,
            circuit_type=CircuitType.PARALLEL,
            size=len(gates),
            name=f"Parallel_{depth}"
        )
    
    @staticmethod
    def grid(side: int) -> BooleanCircuit:
        """2D-Gitter"""
        gates = []
        for i in range(1, side):
            for j in range(side):
                if j == 0:
                    gates.append(("OR", [i-1]))
                else:
                    gates.append(("AND", [i-1, j]))
        
        return BooleanCircuit(
            gates=gates,
            num_inputs=side,
            num_outputs=1,
            circuit_type=CircuitType.GRID,
            size=len(gates),
            name=f"Grid_{side}x{side}"
        )
    
    @staticmethod
    def random(num_gates: int, num_inputs: int = 3) -> BooleanCircuit:
        """Zufällige Verbindungen"""
        gates = []
        gate_types = ["AND", "OR", "NAND", "NOR", "XOR"]
        
        for _ in range(num_gates):
            gate_type = random.choice(gate_types)
            fan_in = random.randint(2, 3)
            inputs = [random.randint(0, num_inputs + len(gates) - 1) for _ in range(fan_in)]
            gates.append((gate_type, inputs))
        
        return BooleanCircuit(
            gates=gates,
            num_inputs=num_inputs,
            num_outputs=1,
            circuit_type=CircuitType.RANDOM,
            size=num_gates,
            name=f"Random_{num_gates}"
        )


if __name__ == "__main__":
    # Test der Masterarbeit-Circuits
    print("Experiment 1: Varying Inputs")
    exp1 = MasterarbeitBenchmark.exp1_vary_inputs()
    for c in exp1[:3]:
        print(f"  {c.name}: {c.num_inputs} inputs, {c.num_gates} gates")
    
    print("\nExperiment 2: Varying Depth")
    exp2 = MasterarbeitBenchmark.exp2_vary_depth()
    for c in exp2[:3]:
        print(f"  {c.name}: m={c.metadata['m']}, depth={c.metadata['depth']}, {c.num_gates} gates")
    
    print("\nTest Circuits:")
    test = TargetANDCircuitGenerator.build_target_and_circuit(4)
    print(f"  {test.name}: {test.num_gates} gates")
