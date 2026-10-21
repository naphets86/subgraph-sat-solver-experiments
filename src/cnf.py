"""
CNF-Kodierung (Tseitin) für Boolean Circuits, DIMACS-Ein-/Ausgabe, Modellprüfung.

Dieses Modul ersetzt die ursprüngliche Kodierung in ``BooleanCircuit.to_dimacs``.
Korrigiert gegenüber der ersten Messreihe (Juli 2026):

- NAND und NOR kodieren jetzt die *negierten* Funktionen von AND bzw. OR
  (zuvor: dasselbe Klauselmuster wie OR bzw. AND).
- XOR kodiert ``y <-> x1 xor x2`` (zuvor ``y <-> not(x1 xor x2)``);
  zusätzlich XNOR und n-äres XOR über eine Kette mit Hilfsvariablen
  (zuvor wurde ab drei Eingängen nur das erste Paar berücksichtigt).
- BUFF-Gates der ISCAS'85-Dateien (1\\,486 Vorkommen) werden kodiert
  (zuvor: keine Klauseln, der Ausgang war unbeschränkt).
- Die redundante Klausel ``(-y v x1 v ... v xk)`` bei AND/OR entfällt;
  sie wird bereits von ``(-y v x_i)`` impliziert.

Variablennummerierung: Knoten ``n`` (Eingang ``n < m``, Gate ``n >= m``)
entspricht der DIMACS-Variable ``n + 1``. Hilfsvariablen folgen danach.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

Clause = List[int]

GATE_TYPES = ("NOT", "BUFF", "AND", "OR", "NAND", "NOR", "XOR", "XNOR")


def _xor_chain(y: int, xs: Sequence[int], new_var: Callable[[], int],
               negate: bool) -> List[Clause]:
    """y <-> x1 xor ... xor xk (bzw. Negation) über Hilfsvariablen."""
    clauses: List[Clause] = []
    acc = xs[0]
    for x in xs[1:-1]:
        t = new_var()
        clauses += _xor2(t, acc, x)
        acc = t
    last = _xor2(y, acc, xs[-1])
    if negate:
        # y <-> not(acc xor b)  ==  (-y) <-> (acc xor b): Literal y in allen Klauseln drehen
        last = [[-l if abs(l) == y else l for l in c] for c in last]
    return clauses + last


def _xor2(y: int, a: int, b: int) -> List[Clause]:
    return [[-y, a, b], [-y, -a, -b], [y, -a, b], [y, a, -b]]


def gate_clauses(gate_type: str, y: int, xs: Sequence[int],
                 new_var: Optional[Callable[[], int]] = None) -> List[Clause]:
    """Klauseln für ``y <-> gate_type(xs)``."""
    t = gate_type.upper()
    xs = list(xs)
    if t in ("BUFF", "BUF"):
        _need(t, xs, 1, exact=True)
        return [[-y, xs[0]], [y, -xs[0]]]
    if t == "NOT":
        _need(t, xs, 1, exact=True)
        return [[-y, -xs[0]], [y, xs[0]]]
    if t == "AND":
        _need(t, xs, 1)
        return [[-y, x] for x in xs] + [[y] + [-x for x in xs]]
    if t == "NAND":
        _need(t, xs, 1)
        return [[y, x] for x in xs] + [[-y] + [-x for x in xs]]
    if t == "OR":
        _need(t, xs, 1)
        return [[y, -x] for x in xs] + [[-y] + xs]
    if t == "NOR":
        _need(t, xs, 1)
        return [[-y, -x] for x in xs] + [[y] + xs]
    if t in ("XOR", "XNOR"):
        _need(t, xs, 2)
        if new_var is None and len(xs) > 2:
            raise ValueError("XOR mit mehr als 2 Eingängen braucht new_var")
        return _xor_chain(y, xs, new_var, negate=(t == "XNOR"))
    raise ValueError(f"Unbekannter Gate-Typ: {gate_type!r}")


def _need(t: str, xs: Sequence[int], n: int, exact: bool = False) -> None:
    ok = len(xs) == n if exact else len(xs) >= n
    if not ok:
        raise ValueError(f"{t} erwartet {'genau ' if exact else 'mindestens '}{n} Eingänge, "
                         f"erhalten: {len(xs)}")


@dataclass
class CNF:
    """CNF-Formel mit Kommentarzeilen."""
    num_vars: int
    clauses: List[Clause] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)

    @property
    def num_clauses(self) -> int:
        return len(self.clauses)

    def to_dimacs(self) -> str:
        lines = [f"c {c}" for c in self.comments]
        lines.append(f"p cnf {self.num_vars} {len(self.clauses)}")
        lines.extend(" ".join(map(str, c)) + " 0" for c in self.clauses)
        return "\n".join(lines) + "\n"


def parse_dimacs(text: str) -> CNF:
    """Liest eine DIMACS-CNF-Datei (Klauseln dürfen über Zeilen verteilt sein)."""
    num_vars = 0
    clauses: List[Clause] = []
    cur: Clause = []
    for line in text.splitlines():
        if not line or line[0] in "c%":
            continue
        if line[0] == "p":
            parts = line.split()
            num_vars = int(parts[2])
            continue
        for tok in line.split():
            v = int(tok)
            if v == 0:
                clauses.append(cur)
                cur = []
            else:
                cur.append(v)
    if cur:
        clauses.append(cur)
    return CNF(num_vars=num_vars, clauses=clauses)


def parse_model(lines: Iterable[str]) -> Dict[int, bool]:
    """Extrahiert ein Modell aus ``v``-Zeilen (SAT-Competition-Format)."""
    model: Dict[int, bool] = {}
    for line in lines:
        # nur echte v-Zeilen ("v 1 -2 0"), nicht z. B. "version ..."
        if not line.startswith("v") or (len(line) > 1 and not line[1].isspace()):
            continue
        for tok in line[1:].split():
            try:
                lit = int(tok)
            except ValueError:
                continue
            if lit != 0:
                model[abs(lit)] = lit > 0
    return model


def check_model(clauses: Iterable[Clause], model: Dict[int, bool]) -> bool:
    """True, wenn das Modell alle Klauseln erfüllt (fehlende Variablen = False)."""
    get = model.get
    for c in clauses:
        for lit in c:
            if get(abs(lit), False) == (lit > 0):
                break
        else:
            return False
    return True
