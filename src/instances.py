"""
Instanzmengen der verbesserten Experimente.

Gegenüber der ersten Messreihe neu:

- Der Circuit-Ausgang wird per Unit-Klausel auf wahr gesetzt
  (``constraint="output"``); die Formeln sind damit nicht mehr trivial erfüllbar.
- Unerfüllbare Instanzen: Miter-Formeln (Circuit gegen eine Kopie seiner selbst;
  ISCAS'85 c499 gegen die funktional äquivalente Variante c1355).
- Größere Circuits bis etwa 10^5 Gates (Target-AND mit bis zu 50\\,000 Eingängen).
- Je Instanz die erwartete Antwort (``expected``), soweit sie aus der
  Konstruktion folgt.

Familien (Feld ``family``):
    target_and         Exp. 1, Ausgang wahr -> SAT (eindeutige Belegung)
    target_and_random  Exp. 2, Ausgang wahr -> Ergebnis nicht vorab bekannt
    iscas85            Exp. 3, erster Ausgang wahr -> nicht vorab bekannt
    miter_self         Circuit gegen sich selbst -> UNSAT
    miter_equiv        c499 gegen c1355 -> UNSAT (äquivalent)
    scaling            Target-AND mit großem m -> SAT
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.boolean_circuits import (
    BooleanCircuit,
    MasterarbeitBenchmark,
    TargetANDCircuitGenerator,
    build_miter,
)


@dataclass
class Instance:
    name: str
    family: str
    circuit: BooleanCircuit
    constraint: str = "output"
    expected: Optional[str] = None           # "SAT", "UNSAT" oder None (unbekannt)
    params: Dict = field(default_factory=dict)


@dataclass(frozen=True)
class Preset:
    name: str
    repetitions: int
    warmup: int
    timeout: float
    budget_s: float          # Zeitbudget je Instanz für die Wiederholungen
    description: str


PRESETS = {
    "quick": Preset("quick", 5, 1, 20.0, 10.0, "Funktionstest (wenige Instanzen, 5 Wiederholungen)"),
    "standard": Preset("standard", 15, 2, 30.0, 30.0, "Exp. 1-3 und Miter, 15 Wiederholungen"),
    "full": Preset("full", 30, 3, 60.0, 60.0, "Exp. 1-3, Miter und Skalierung, 30 Wiederholungen"),
    "scaling": Preset("scaling", 10, 2, 120.0, 120.0, "Nur Skalierung bis 10^5 Gates"),
}

SCALING_M = [100, 500, 1000, 5000, 10000, 20000, 50000]


def _target_and(m: int, family: str = "target_and") -> Instance:
    c = TargetANDCircuitGenerator.build_target_and_circuit(m)
    return Instance(c.name, family, c, "output", "SAT", {"m": m})


def exp1() -> List[Instance]:
    return [_target_and(m) for m in range(4, 21, 2)]


def exp2(m: int = 10) -> List[Instance]:
    out = []
    for c in MasterarbeitBenchmark.exp2_vary_depth(m):
        out.append(Instance(c.name, "target_and_random", c, "output", None,
                            {"m": m, "depth": c.metadata["depth"]}))
    return out


def exp3() -> List[Instance]:
    return [Instance(c.name, "iscas85", c, "output", None, {})
            for c in MasterarbeitBenchmark.exp3_iscas85()]


def miters(quick: bool = False) -> List[Instance]:
    out: List[Instance] = []
    for m in ([10] if quick else [10, 20]):
        c = TargetANDCircuitGenerator.build_target_and_circuit(m)
        out.append(Instance(f"MiterSelf_{c.name}", "miter_self",
                            build_miter(c, c, f"MiterSelf_{c.name}"), "output", "UNSAT", {"m": m}))
    by_name = {c.name: c for c in MasterarbeitBenchmark.exp3_iscas85()}
    self_names = ["c17", "c432"] if quick else ["c17", "c432", "c499", "c880", "c1355", "c1908"]
    for n in self_names:
        c = by_name[n]
        out.append(Instance(f"MiterSelf_{n}", "miter_self",
                            build_miter(c, c, f"MiterSelf_{n}"), "output", "UNSAT", {}))
    if "c499" in by_name and "c1355" in by_name:
        out.append(Instance("Miter_c499_c1355", "miter_equiv",
                            build_miter(by_name["c499"], by_name["c1355"], "Miter_c499_c1355"),
                            "output", "UNSAT", {}))
    return out


def scaling(sizes=SCALING_M) -> List[Instance]:
    return [_target_and(m, "scaling") for m in sizes]


def build_instances(preset: str) -> List[Instance]:
    if preset == "quick":
        e1 = [i for i in exp1() if i.params["m"] in (4, 10, 20)]
        e2 = [i for i in exp2() if i.params["depth"] in (1, 6, 12)]
        e3 = [i for i in exp3() if i.name in ("c17", "c432")]
        return e1 + e2 + e3 + miters(quick=True)
    if preset == "standard":
        return exp1() + exp2() + exp3() + miters()
    if preset == "full":
        return exp1() + exp2() + exp3() + miters() + scaling([100, 1000, 10000, 50000])
    if preset == "scaling":
        return scaling()
    raise ValueError(f"Unbekanntes Preset: {preset}")
