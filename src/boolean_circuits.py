"""
Boolean Circuit Generator für Subgraph-SAT-Solver Experimente

Generiert die EXAKTEN Boolean Circuits aus der Masterarbeit:
- Target-AND Circuits (LBV-Zielassignments) - Exp 1
- Target-AND mit Random Intermediate Layers - Exp 2
- ISCAS'85 Benchmarks - Exp 3
- Zusätzliche: Sequential, Parallel, Grid, Random

Basiert auf: Epp, S. (2013). "Learning M-DNF in Boolean Circuits"
"""

from typing import List, Tuple, Set, Dict, Optional, Sequence
from pathlib import Path
import random
import math
from dataclasses import dataclass
from enum import Enum

from src import ISCAS85_DIR
from src.cnf import CNF, gate_clauses

CONSTRAINTS = ("none", "output", "all_outputs")


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
    MITER = "miter"                     # Äquivalenzprüfung zweier Circuits (UNSAT bei Gleichheit)


_COMMENT_VALUE_MAX = 200


@dataclass
class BooleanCircuit:
    """Repräsentation eines Boolean Circuits.

    Knotennummerierung: Eingang ``n < num_inputs``, Gate ``g`` (0-basiert in
    ``gates``) hat die Knotennummer ``num_inputs + g``. Gate-Eingänge sind
    Knotennummern früherer Knoten (topologische Reihenfolge).
    ``outputs`` enthält die Knotennummern der Ausgänge (Standard: letztes Gate).
    """
    gates: List[Tuple[str, List[int]]]  # [(gate_type, input_indices), ...]
    num_inputs: int
    num_outputs: int
    circuit_type: CircuitType
    size: int
    name: str = ""
    metadata: Dict = None  # Zusätzliche Informationen (z.B. depth, m, etc.)
    outputs: Optional[List[int]] = None
    input_names: Optional[List[str]] = None
    output_names: Optional[List[str]] = None

    def __post_init__(self):
        self.num_gates = len(self.gates)
        if self.metadata is None:
            self.metadata = {}
        if self.outputs is None:
            self.outputs = [self.num_inputs + self.num_gates - 1] if self.gates else []
        self.num_outputs = len(self.outputs)

    # ------------------------------------------------------------------ CNF
    def to_cnf(self, constraint: str = "output") -> CNF:
        """Tseitin-Kodierung (siehe ``src.cnf``).

        constraint:
            ``"none"``         keine Ausgangsbedingung (trivial erfüllbar)
            ``"output"``       erster Ausgang wird per Unit-Klausel auf wahr gesetzt
            ``"all_outputs"``  alle Ausgänge wahr
        """
        if constraint not in CONSTRAINTS:
            raise ValueError(f"Unbekannte Ausgangsbedingung: {constraint!r} (erlaubt: {CONSTRAINTS})")
        m = self.num_inputs
        last = [m + len(self.gates)]

        def new_var() -> int:
            last[0] += 1
            return last[0]

        clauses: List[List[int]] = []
        for idx, (gate_type, inputs) in enumerate(self.gates):
            clauses.extend(gate_clauses(gate_type, m + idx + 1, [i + 1 for i in inputs], new_var))
        if constraint == "output" and self.outputs:
            clauses.append([self.outputs[0] + 1])
        elif constraint == "all_outputs":
            clauses.extend([o + 1] for o in self.outputs)

        comments = [f"Circuit: {self.name or self.circuit_type.value}",
                    f"Type: {self.circuit_type.value}", f"constraint: {constraint}"]
        for key, value in self.metadata.items():
            text = str(value).replace("\n", " ")
            if len(text) <= _COMMENT_VALUE_MAX:
                comments.append(f"{key}: {text}")
        return CNF(num_vars=last[0], clauses=clauses, comments=comments)

    def to_dimacs(self, constraint: str = "output") -> str:
        """DIMACS-Text; Standard ist die Formel mit Ausgangsbedingung."""
        return self.to_cnf(constraint).to_dimacs()

    # ------------------------------------------------------------ Evaluation
    def evaluate(self, input_values: Sequence[bool]) -> List[bool]:
        """Wertet den Circuit aus; liefert die Werte aller Ausgänge."""
        m = self.num_inputs
        if len(input_values) != m:
            raise ValueError(f"{m} Eingabewerte erwartet, erhalten: {len(input_values)}")
        val = [bool(v) for v in input_values]
        for gate_type, ins in self.gates:
            xs = [val[i] for i in ins]
            t = gate_type.upper()
            if t in ("BUFF", "BUF"):
                r = xs[0]
            elif t == "NOT":
                r = not xs[0]
            elif t == "AND":
                r = all(xs)
            elif t == "NAND":
                r = not all(xs)
            elif t == "OR":
                r = any(xs)
            elif t == "NOR":
                r = not any(xs)
            elif t == "XOR":
                r = sum(xs) % 2 == 1
            elif t == "XNOR":
                r = sum(xs) % 2 == 0
            else:
                raise ValueError(f"Unbekannter Gate-Typ: {gate_type!r}")
            val.append(r)
        return [val[o] for o in self.outputs]

    def check_model(self, model: Dict[int, bool], constraint: str = "output") -> bool:
        """Prüft ein Solver-Modell gegen den *Circuit* (nicht gegen die CNF):
        Die Eingänge werden aus dem Modell gelesen, der Circuit wird ausgewertet
        und die Ausgangsbedingung geprüft."""
        values = [model.get(i + 1, False) for i in range(self.num_inputs)]
        outs = self.evaluate(values)
        if constraint == "none" or not outs:
            return True
        return outs[0] if constraint == "output" else all(outs)


def build_miter(a: BooleanCircuit, b: BooleanCircuit, name: str = "") -> BooleanCircuit:
    """Miter zweier Circuits: Gemeinsame Eingänge, Ausgang = OR über die XORs
    entsprechender Ausgänge. Mit Ausgangsbedingung "output" ist die Formel genau
    dann erfüllbar, wenn sich die Circuits auf mindestens einer Eingabe
    unterscheiden (UNSAT = funktional äquivalent).

    Eingänge/Ausgänge werden über ihre Namen zugeordnet (falls beide Circuits
    Namen besitzen und die Namensmengen übereinstimmen), sonst nach Position.
    """
    m = a.num_inputs
    if b.num_inputs != m or len(a.outputs) != len(b.outputs) or not a.outputs:
        raise ValueError("Miter: Eingangs- und Ausgangszahl müssen übereinstimmen")

    def order(names_a, names_b, n):
        if names_a and names_b and len(names_a) == n and sorted(names_a) == sorted(names_b):
            pos = {nm: i for i, nm in enumerate(names_a)}
            return [pos[nm] for nm in names_b]      # Index in a für das j-te Element von b
        return list(range(n))

    in_map = order(a.input_names, b.input_names, m)
    out_map = order(a.output_names, b.output_names, len(a.outputs))

    off = len(a.gates)
    gates = [(t, list(ins)) for t, ins in a.gates]
    for t, ins in b.gates:
        gates.append((t, [in_map[i] if i < m else i + off for i in ins]))

    def b_node(n: int) -> int:
        return in_map[n] if n < m else n + off

    xors = []
    for j, bo in enumerate(b.outputs):
        gates.append(("XOR", [a.outputs[out_map[j]], b_node(bo)]))
        xors.append(m + len(gates) - 1)
    if len(xors) > 1:
        gates.append(("OR", xors))
    out_node = m + len(gates) - 1
    return BooleanCircuit(
        gates=gates, num_inputs=m, num_outputs=1, circuit_type=CircuitType.MITER,
        size=len(gates), name=name or f"Miter_{a.name}_{b.name}",
        metadata={"a": a.name, "b": b.name, "compared_outputs": len(xors)},
        outputs=[out_node],
        input_names=list(a.input_names) if a.input_names else None,
    )


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
            outputs=[output_idx],
            metadata={
                "m": m,
                "lbv_rounds": TargetANDCircuitGenerator.lbv_round_count(m),
                **({"satisfying_assignment": str(target)} if m <= 64 else {}),
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
            outputs=[output_idx],
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
    def parse_bench(text: str, name: str = "bench") -> BooleanCircuit:
        """Parst eine ISCAS-.bench-Beschreibung.

        Knotennummern: Eingänge in Deklarationsreihenfolge, danach die Gates in
        topologischer Reihenfolge. Gate-Typen werden unverändert übernommen
        (AND, NAND, OR, NOR, XOR, XNOR, NOT, BUFF). Die Ausgänge werden über ihre
        Signalnamen aufgelöst (``outputs``).
        """
        inputs: List[str] = []
        outputs: List[str] = []
        defs: Dict[str, Tuple[str, List[str]]] = {}
        order: List[str] = []
        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            up = line.upper()
            if up.startswith("INPUT"):
                inputs.append(line[line.index("(") + 1:line.rindex(")")].strip())
            elif up.startswith("OUTPUT"):
                outputs.append(line[line.index("(") + 1:line.rindex(")")].strip())
            elif "=" in line:
                lhs, rhs = line.split("=", 1)
                lhs = lhs.strip()
                gate_type = rhs[:rhs.index("(")].strip().upper()
                if gate_type == "BUF":
                    gate_type = "BUFF"
                args = [a.strip() for a in rhs[rhs.index("(") + 1:rhs.rindex(")")].split(",") if a.strip()]
                if lhs in defs or lhs in inputs:
                    raise ValueError(f"{name}, Zeile {lineno}: Signal {lhs!r} doppelt definiert")
                defs[lhs] = (gate_type, args)
                order.append(lhs)
            else:
                raise ValueError(f"{name}, Zeile {lineno}: nicht erkannt: {raw!r}")

        node: Dict[str, int] = {n: i for i, n in enumerate(inputs)}
        m = len(inputs)
        gates: List[Tuple[str, List[int]]] = []
        pending = order
        while pending:                                  # topologische Sortierung
            rest = []
            for sig in pending:
                gate_type, args = defs[sig]
                if all(a in node for a in args):
                    node[sig] = m + len(gates)
                    gates.append((gate_type, [node[a] for a in args]))
                else:
                    rest.append(sig)
            if len(rest) == len(pending):
                missing = {a for s_ in rest for a in defs[s_][1] if a not in node and a not in defs}
                raise ValueError(f"{name}: undefinierte Signale oder Zyklus: {sorted(missing)[:5] or rest[:5]}")
            pending = rest
        for o in outputs:
            if o not in node:
                raise ValueError(f"{name}: Ausgang {o!r} nicht definiert")

        return BooleanCircuit(
            gates=gates, num_inputs=m, num_outputs=len(outputs),
            circuit_type=CircuitType.ISCAS85, size=len(gates), name=name,
            metadata={"benchmark": "ISCAS'85"},
            outputs=[node[o] for o in outputs],
            input_names=list(inputs), output_names=list(outputs),
        )

    @staticmethod
    def load_bench_file(file_path: Path) -> BooleanCircuit:
        """Lädt eine Standard-.bench-Datei als BooleanCircuit."""
        file_path = Path(file_path)
        c = MasterarbeitBenchmark.parse_bench(file_path.read_text(encoding="utf-8"), file_path.stem)
        c.metadata["original_file"] = file_path.name
        return c

    @staticmethod
    def exp3_iscas85() -> List[BooleanCircuit]:
        """Lädt automatisch alle .bench-Dateien aus dem Ordner src/iscas85/"""
        circuits = []
        iscas_dir = ISCAS85_DIR
        
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
