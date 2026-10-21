"""Tseitin-Kodierung: jede Gate-Funktion gegen ihre Wahrheitstabelle."""
import itertools
import unittest

from src.cnf import GATE_TYPES, CNF, check_model, gate_clauses, parse_dimacs, parse_model

FUNCS = {
    "AND": all, "NAND": lambda xs: not all(xs), "OR": any, "NOR": lambda xs: not any(xs),
    "XOR": lambda xs: sum(xs) % 2 == 1, "XNOR": lambda xs: sum(xs) % 2 == 0,
    "NOT": lambda xs: not xs[0], "BUFF": lambda xs: xs[0],
}


def _arities(t):
    if t in ("NOT", "BUFF"):
        return [1]
    if t in ("XOR", "XNOR"):
        return [2, 3, 4]
    return [1, 2, 3, 4]


class TestCnf(unittest.TestCase):
    def test_gate_truth_tables(self):
        for gate in GATE_TYPES:
            for k in _arities(gate):
                with self.subTest(gate=gate, arity=k):
                    xs, y = list(range(1, k + 1)), k + 1
                    last = [y]

                    def new_var():
                        last[0] += 1
                        return last[0]

                    clauses = gate_clauses(gate, y, xs, new_var)
                    aux = list(range(y + 1, last[0] + 1))
                    for bits in itertools.product([False, True], repeat=k):
                        for yv in (False, True):
                            satisfiable = any(
                                check_model(clauses, {**{i + 1: b for i, b in enumerate(bits)}, y: yv,
                                                      **dict(zip(aux, ab))})
                                for ab in itertools.product([False, True], repeat=len(aux)))
                            self.assertEqual(satisfiable, yv == FUNCS[gate](list(bits)), (bits, yv))

    def test_xor2_needs_no_aux_variable(self):
        self.assertTrue(gate_clauses("XOR", 3, [1, 2]))
        with self.assertRaises(ValueError):
            gate_clauses("XOR", 4, [1, 2, 3])

    def test_arity_and_type_errors(self):
        with self.assertRaises(ValueError):
            gate_clauses("NOT", 3, [1, 2])
        with self.assertRaises(ValueError):
            gate_clauses("FOO", 3, [1])

    def test_parse_model_ignores_non_model_lines(self):
        self.assertEqual(parse_model(["version 3", "v 1 -2 0", "vv", "v 3"]),
                         {1: True, 2: False, 3: True})

    def test_dimacs_roundtrip(self):
        cnf = CNF(3, [[1, -2], [2, 3, -1]], ["x"])
        back = parse_dimacs(cnf.to_dimacs())
        self.assertEqual((back.num_vars, back.clauses), (3, cnf.clauses))


if __name__ == "__main__":
    unittest.main()
