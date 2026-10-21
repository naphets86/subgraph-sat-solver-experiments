#!/usr/bin/env python3
"""
Referenz-SAT-Solver (CDCL) in reinem Python.

Zweck: Ein kleiner, korrekter und überall verfügbarer Solver, der dasselbe
Aufrufprotokoll wie ein externer Solver verwendet (``solver datei.cnf``,
Ausgabe im SAT-Competition-Format). Er dient

- als Referenz für die Korrektheitsprüfung (SAT/UNSAT, Modellprüfung),
- als Vergleichssolver, solange MiniSat/CaDiCaL nicht installiert sind,
- zum Testen des gesamten Messaufbaus ohne den Subgraph-SAT-Solver.

Er ist *nicht* auf Geschwindigkeit ausgelegt und mit MiniSat/CaDiCaL nicht
konkurrenzfähig. Messwerte dieses Solvers sagen nichts über den
Subgraph-SAT-Solver aus.

Aufruf::

    python -m src.reference_solver instanz.cnf

Ausgabe: ``s SATISFIABLE`` / ``s UNSATISFIABLE``, bei SAT ``v``-Zeilen mit dem
Modell; Rückgabecode 10 (SAT) bzw. 20 (UNSAT) wie in der SAT-Competition.

Algorithmus: Zwei-Watched-Literals-Propagation, 1-UIP-Lernen mit
nicht-chronologischem Backjumping, VSIDS (Lazy-Heap), Phase-Saving,
Luby-Restarts, gelegentliches Löschen langer gelernter Klauseln.
"""

import heapq
import sys
from typing import List, Optional

__version__ = "1.0"


def _luby(i: int) -> int:
    k = 1
    while (1 << k) - 1 < i + 1:
        k += 1
    while True:
        if i + 1 == (1 << k) - 1:
            return 1 << (k - 1)
        i -= (1 << (k - 1)) - 1
        k = 1
        while (1 << k) - 1 < i + 1:
            k += 1


class CDCLSolver:
    """Literale: Variable v (0-basiert) -> 2v (positiv), 2v+1 (negativ)."""

    def __init__(self, num_vars: int):
        self.n = num_vars
        self.val = [0] * (2 * num_vars)          # 1 wahr, -1 falsch, 0 offen
        self.level = [0] * num_vars
        self.reason: List[Optional[int]] = [None] * num_vars
        self.trail: List[int] = []
        self.trail_lim: List[int] = []
        self.qhead = 0
        self.clauses: List[List[int]] = []
        self.learnt_idx: List[int] = []
        self.watches: List[List[int]] = [[] for _ in range(2 * num_vars)]
        self.activity = [0.0] * num_vars
        self.var_inc = 1.0
        self.phase = [1] * num_vars              # 1 = zuerst negativ
        self.heap = [(0.0, v) for v in range(num_vars)]
        heapq.heapify(self.heap)
        self.ok = True
        self.conflicts = 0

    # ------------------------------------------------------------ Klauseln
    def add_clause(self, lits: List[int]) -> None:
        if not self.ok:
            return
        seen = set()
        clause = []
        for l in lits:
            if (l ^ 1) in seen:
                return                              # Tautologie
            if l not in seen:
                seen.add(l)
                clause.append(l)
        if not clause:
            self.ok = False
            return
        if len(clause) == 1:
            if self.val[clause[0]] == -1:
                self.ok = False
            elif self.val[clause[0]] == 0:
                self._enqueue(clause[0], None)
            return
        ci = len(self.clauses)
        self.clauses.append(clause)
        self.watches[clause[0]].append(ci)
        self.watches[clause[1]].append(ci)

    def _enqueue(self, lit: int, reason: Optional[int]) -> None:
        self.val[lit] = 1
        self.val[lit ^ 1] = -1
        v = lit >> 1
        self.level[v] = len(self.trail_lim)
        self.reason[v] = reason
        self.trail.append(lit)

    # ---------------------------------------------------------- Propagation
    def _propagate(self) -> Optional[int]:
        val, watches, clauses, trail = self.val, self.watches, self.clauses, self.trail
        while self.qhead < len(trail):
            p = trail[self.qhead]
            self.qhead += 1
            fl = p ^ 1
            ws = watches[fl]
            i = j = 0
            n = len(ws)
            while i < n:
                ci = ws[i]
                i += 1
                c = clauses[ci]
                if c[0] == fl:
                    c[0], c[1] = c[1], fl
                first = c[0]
                if val[first] == 1:
                    ws[j] = ci
                    j += 1
                    continue
                for k in range(2, len(c)):
                    if val[c[k]] != -1:
                        c[1], c[k] = c[k], fl
                        watches[c[1]].append(ci)
                        break
                else:
                    ws[j] = ci
                    j += 1
                    if val[first] == -1:
                        while i < n:
                            ws[j] = ws[i]
                            j += 1
                            i += 1
                        del ws[j:]
                        self.qhead = len(trail)
                        return ci
                    self._enqueue(first, ci)
            del ws[j:]
        return None

    # --------------------------------------------------------------- Lernen
    def _analyze(self, confl: int):
        seen = [False] * self.n
        learnt = [0]
        counter = 0
        p = -1
        idx = len(self.trail) - 1
        cur_level = len(self.trail_lim)
        ci = confl
        while True:
            c = self.clauses[ci]
            for q in c:
                if p != -1 and q == p:
                    continue
                v = q >> 1
                if not seen[v] and self.level[v] > 0:
                    seen[v] = True
                    self._bump(v)
                    if self.level[v] >= cur_level:
                        counter += 1
                    else:
                        learnt.append(q)
            while not seen[self.trail[idx] >> 1]:
                idx -= 1
            p = self.trail[idx]
            idx -= 1
            v = p >> 1
            seen[v] = False
            counter -= 1
            if counter == 0:
                break
            ci = self.reason[v]
        learnt[0] = p ^ 1
        if len(learnt) == 1:
            back = 0
        else:
            m = max(range(1, len(learnt)), key=lambda k: self.level[learnt[k] >> 1])
            learnt[1], learnt[m] = learnt[m], learnt[1]
            back = self.level[learnt[1] >> 1]
        return learnt, back

    def _bump(self, v: int) -> None:
        self.activity[v] += self.var_inc
        if self.activity[v] > 1e100:
            self.activity = [a * 1e-100 for a in self.activity]
            self.var_inc *= 1e-100
            self.heap = [(-self.activity[u], u) for u in range(self.n) if self.val[2 * u] == 0]
            heapq.heapify(self.heap)
        elif self.val[2 * v] == 0:
            heapq.heappush(self.heap, (-self.activity[v], v))

    def _backtrack(self, level: int) -> None:
        if len(self.trail_lim) <= level:
            return
        lim = self.trail_lim[level]
        for lit in reversed(self.trail[lim:]):
            v = lit >> 1
            self.phase[v] = lit & 1
            self.val[lit] = 0
            self.val[lit ^ 1] = 0
            heapq.heappush(self.heap, (-self.activity[v], v))
        del self.trail[lim:]
        del self.trail_lim[level:]
        self.qhead = lim

    def _pick(self) -> int:
        heap, val = self.heap, self.val
        while heap:
            _, v = heapq.heappop(heap)
            if val[2 * v] == 0:
                return 2 * v + self.phase[v]
        return -1

    def _reduce(self) -> None:
        """Entfernt die Hälfte der langen gelernten Klauseln (nicht Gründe)."""
        locked = {r for r in self.reason if r is not None}
        cand = [ci for ci in self.learnt_idx
                if len(self.clauses[ci]) > 3 and ci not in locked]
        drop = set(cand[: len(cand) // 2])
        if not drop:
            return
        for lit in range(2 * self.n):
            ws = self.watches[lit]
            if ws:
                self.watches[lit] = [ci for ci in ws if ci not in drop]
        for ci in drop:
            self.clauses[ci] = [0, 0]                # Platzhalter, nie beobachtet
        self.learnt_idx = [ci for ci in self.learnt_idx if ci not in drop]

    # ---------------------------------------------------------------- Suche
    def solve(self) -> bool:
        if not self.ok or self._propagate() is not None:
            return False
        restart_no = 0
        budget = 100 * _luby(restart_no)
        since_restart = 0
        max_learnts = max(2000, len(self.clauses) // 3)
        while True:
            confl = self._propagate()
            if confl is not None:
                self.conflicts += 1
                since_restart += 1
                if not self.trail_lim:
                    return False
                learnt, back = self._analyze(confl)
                self._backtrack(back)
                if len(learnt) == 1:
                    self._enqueue(learnt[0], None)
                else:
                    ci = len(self.clauses)
                    self.clauses.append(learnt)
                    self.learnt_idx.append(ci)
                    self.watches[learnt[0]].append(ci)
                    self.watches[learnt[1]].append(ci)
                    self._enqueue(learnt[0], ci)
                self.var_inc *= 1.0 / 0.95
            else:
                if since_restart >= budget:
                    restart_no += 1
                    budget = 100 * _luby(restart_no)
                    since_restart = 0
                    self._backtrack(0)
                    if len(self.learnt_idx) > max_learnts:
                        self._reduce()
                        max_learnts = int(max_learnts * 1.3)
                    continue
                lit = self._pick()
                if lit == -1:
                    return True
                self.trail_lim.append(len(self.trail))
                self._enqueue(lit, None)

    def model(self) -> List[int]:
        return [(v + 1) if self.val[2 * v] == 1 else -(v + 1) for v in range(self.n)]


def read_dimacs(path: str):
    """Schnelles Einlesen; liefert (num_vars, Klauselliste in Literalkodierung)."""
    num_vars = 0
    clauses: List[List[int]] = []
    cur: List[int] = []
    with open(path, "r") as f:
        for line in f:
            if not line.strip() or line[0] in "c%":
                continue
            if line[0] == "p":
                num_vars = int(line.split()[2])
                continue
            for tok in line.split():
                x = int(tok)
                if x == 0:
                    clauses.append(cur)
                    cur = []
                else:
                    cur.append(2 * (abs(x) - 1) + (1 if x < 0 else 0))
    if cur:
        clauses.append(cur)
    return num_vars, clauses


def main(argv: List[str]) -> int:
    if len(argv) >= 2 and argv[1] in ("--help", "-h"):
        print(__doc__)
        return 0
    if len(argv) >= 2 and argv[1] == "--version":
        print(f"reference-cdcl {__version__}")
        return 0
    if len(argv) < 2:
        print("Aufruf: python -m src.reference_solver datei.cnf", file=sys.stderr)
        return 2
    sys.setrecursionlimit(10000)
    num_vars, clauses = read_dimacs(argv[1])
    solver = CDCLSolver(num_vars)
    for c in clauses:
        solver.add_clause(c)
    if solver.solve():
        print("s SATISFIABLE")
        model = solver.model()
        for i in range(0, len(model), 20):
            print("v " + " ".join(map(str, model[i:i + 20])))
        print("v 0")
        return 10
    print("s UNSATISFIABLE")
    return 20


if __name__ == "__main__":
    sys.exit(main(sys.argv))
